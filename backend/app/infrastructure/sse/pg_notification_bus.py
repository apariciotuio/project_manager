"""Postgres LISTEN/NOTIFY pub/sub bus for SSE channel management.

Replaces RedisPubSub. Interface is identical:
  publish(channel, message)  — serializes to JSON and calls pg_notify.
  subscribe(channel)         — async iterator yielding deserialized dicts.

Connection model
----------------
publish() uses a pooled asyncpg connection acquired from the pool for the
duration of the call only.

subscribe() acquires a **dedicated** asyncpg connection that is NOT returned
to the pool for the life of the subscription — LISTEN holds the connection.
UNLISTEN + close happen in the finally block of the async generator.

Payload limit
-------------
Postgres NOTIFY payloads are capped at 8000 bytes. Payloads exceeding this
limit raise PayloadTooLarge before the call hits the wire.

Single-worker constraint
------------------------
LISTEN/NOTIFY is per-connection: messages are delivered only to the Postgres
connection that issued LISTEN. This is fine for single-worker Uvicorn.
Multi-worker deployments need a shared broker — document this before scaling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

_MAX_PAYLOAD_BYTES = 8000

# Postgres identifier limit is 63 bytes. Allowlist: alphanumeric, underscore,
# colon (sse:job: prefix), hyphen (UUIDs), dot. No quotes, spaces, or SQL metacharacters.
_CHANNEL_PATTERN = re.compile(r"^[A-Za-z0-9_:.\-]{1,63}$")


def _validate_channel(channel: str) -> None:
    """Raise ValueError if *channel* is not a safe Postgres identifier."""
    if not _CHANNEL_PATTERN.match(channel):
        raise ValueError(f"invalid channel name: {channel!r}")


class PayloadTooLarge(Exception):
    """Raised when a NOTIFY payload exceeds the 8000-byte Postgres limit."""


class PgNotificationBus:
    """Pub/sub backed by Postgres LISTEN/NOTIFY.

    Args:
        dsn: asyncpg-compatible DSN string, e.g.
             ``postgresql://user:pass@host:port/db``.
             The DSN must NOT use the SQLAlchemy ``postgresql+asyncpg://`` prefix.
        pool: Pre-existing asyncpg pool. Mutually exclusive with ``dsn``.
              If neither is provided, a single-use connection is created per
              call (test mode only — inefficient in production).

    Exactly one of ``dsn`` or ``pool`` must be provided in production.
    """

    def __init__(
        self,
        *,
        dsn: str | None = None,
        pool: asyncpg.Pool | None = None,  # type: ignore[type-arg]
    ) -> None:
        if dsn is None and pool is None:
            raise ValueError("Provide either dsn or pool")
        if dsn is not None and pool is not None:
            raise ValueError("Provide either dsn or pool, not both")
        self._dsn = dsn
        self._pool = pool

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _acquire_pooled(self) -> asyncpg.Connection:  # type: ignore[type-arg]
        """Acquire a connection for publish (short-lived, returns to pool)."""
        if self._pool is not None:
            return await self._pool.acquire()  # type: ignore[return-value]
        return await asyncpg.connect(self._dsn)

    async def _release_pooled(self, conn: asyncpg.Connection) -> None:  # type: ignore[type-arg]
        if self._pool is not None:
            await self._pool.release(conn)
        else:
            await conn.close()

    async def _acquire_dedicated(self) -> asyncpg.Connection:  # type: ignore[type-arg]
        """Acquire a dedicated connection for LISTEN (lives for subscription duration)."""
        if self._pool is not None:
            # asyncpg pool.acquire() in isolation mode keeps the connection
            # out of the pool until explicitly released.
            return await self._pool.acquire()  # type: ignore[return-value]
        return await asyncpg.connect(self._dsn)

    async def _release_dedicated(self, conn: asyncpg.Connection) -> None:  # type: ignore[type-arg]
        if self._pool is not None:
            await self._pool.release(conn)
        else:
            await conn.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Serialize *message* to JSON and issue pg_notify on *channel*.

        Raises ValueError for invalid channel names (SQL-injection defense).
        Raises PayloadTooLarge when the JSON payload exceeds 8000 bytes.
        """
        _validate_channel(channel)
        payload = {**message, "channel": channel}
        raw = json.dumps(payload)
        if len(raw.encode()) > _MAX_PAYLOAD_BYTES:
            raise PayloadTooLarge(
                f"NOTIFY payload {len(raw.encode())} bytes exceeds {_MAX_PAYLOAD_BYTES} limit. "
                "Publish a reference ID and fetch from DB instead."
            )
        conn = await self._acquire_pooled()
        try:
            await conn.execute("SELECT pg_notify($1, $2)", channel, raw)
            logger.debug("pg_notify channel=%s payload_bytes=%d", channel, len(raw.encode()))
        finally:
            await self._release_pooled(conn)

    async def subscribe(
        self,
        channel: str,
        max_messages: int | None = None,
        poll_interval: float = 0.05,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield deserialized dicts from Postgres NOTIFY events on *channel*.

        Acquires a dedicated connection, issues LISTEN, then yields each
        incoming notification.  On generator close (client disconnect,
        CancelledError, or max_messages exhausted) issues UNLISTEN and
        closes the connection.

        The ``max_messages`` and ``poll_interval`` parameters mirror the
        RedisPubSub interface so SseHandler and tests require no changes.
        """
        _validate_channel(channel)
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        def _listener(
            connection: asyncpg.Connection,  # type: ignore[type-arg]
            pid: int,
            ch: str,
            payload: str,
        ) -> None:
            try:
                data = json.loads(payload)
            except (json.JSONDecodeError, ValueError):
                logger.warning("pg_notify: invalid JSON on channel=%s payload=%r", ch, payload)
                return
            queue.put_nowait(data)

        conn = await self._acquire_dedicated()
        try:
            await conn.add_listener(channel, _listener)
            await conn.execute(f'LISTEN "{channel}"')
            logger.debug("LISTEN channel=%s", channel)

            count = 0
            while max_messages is None or count < max_messages:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=poll_interval)
                    yield data
                    count += 1
                except TimeoutError:
                    if max_messages is not None:
                        # bounded iteration with no message — keep waiting
                        continue
                    # unbounded — keep polling (caller controls via CancelledError)
                    continue
                except asyncio.CancelledError:
                    logger.debug("SSE client disconnected from channel=%s", channel)
                    raise
        finally:
            try:
                await conn.execute(f'UNLISTEN "{channel}"')
                await conn.remove_listener(channel, _listener)
            except Exception:  # noqa: BLE001 — best-effort cleanup; connection may be closed
                pass
            await self._release_dedicated(conn)
            logger.debug("UNLISTEN + release channel=%s", channel)
