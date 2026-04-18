"""Integration test — real Postgres LISTEN/NOTIFY roundtrip.

Publish on one connection (via PgNotificationBus.publish), subscribe on
another (PgNotificationBus.subscribe), assert the message arrives.

Uses the session-scoped testcontainer Postgres from conftest.py.
No migrations needed — LISTEN/NOTIFY is built-in to Postgres.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.infrastructure.sse.pg_notification_bus import PayloadTooLarge, PgNotificationBus

# ---------------------------------------------------------------------------
# Fixture: plain asyncpg DSN from the test settings
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def asyncpg_dsn(override_settings) -> str:  # type: ignore[type-arg]
    """Return a plain asyncpg DSN (strip SQLAlchemy prefix)."""
    url: str = override_settings.database.url
    return url.replace("postgresql+asyncpg://", "postgresql://")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect_one(
    bus: PgNotificationBus, channel: str, timeout: float = 5.0
) -> dict[str, Any]:
    """Subscribe and return the first message, raising TimeoutError if none arrives."""
    received: list[dict[str, Any]] = []

    async def _consume() -> None:
        async for msg in bus.subscribe(channel, max_messages=1):
            received.append(msg)

    await asyncio.wait_for(_consume(), timeout=timeout)
    return received[0]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_subscribe_roundtrip(asyncpg_dsn: str) -> None:
    """Publish on bus A, subscribe on bus B, assert message arrives."""
    publisher = PgNotificationBus(dsn=asyncpg_dsn)
    subscriber = PgNotificationBus(dsn=asyncpg_dsn)

    channel = "sse:test:roundtrip"
    message = {"type": "token", "payload": {"text": "hello from pg_notify"}}

    received: list[dict[str, Any]] = []

    async def _subscribe() -> None:
        async for msg in subscriber.subscribe(channel, max_messages=1):
            received.append(msg)

    # Start subscriber first, then publish
    task = asyncio.create_task(_subscribe())
    await asyncio.sleep(0.05)  # give LISTEN time to register

    await publisher.publish(channel, message)

    await asyncio.wait_for(task, timeout=5.0)

    assert len(received) == 1
    assert received[0]["type"] == "token"
    assert received[0]["payload"]["text"] == "hello from pg_notify"
    assert received[0]["channel"] == channel


@pytest.mark.asyncio
async def test_multiple_messages_on_same_channel(asyncpg_dsn: str) -> None:
    publisher = PgNotificationBus(dsn=asyncpg_dsn)
    subscriber = PgNotificationBus(dsn=asyncpg_dsn)

    channel = "sse:test:multi"
    messages = [
        {"type": "progress", "payload": {"pct": 25}},
        {"type": "progress", "payload": {"pct": 75}},
        {"type": "done", "payload": {"message_id": "fin"}},
    ]

    received: list[dict[str, Any]] = []

    async def _subscribe() -> None:
        async for msg in subscriber.subscribe(channel, max_messages=3):
            received.append(msg)

    task = asyncio.create_task(_subscribe())
    await asyncio.sleep(0.05)

    for msg in messages:
        await publisher.publish(channel, msg)
        await asyncio.sleep(0.01)

    await asyncio.wait_for(task, timeout=5.0)

    assert len(received) == 3
    assert received[0]["type"] == "progress"
    assert received[1]["payload"]["pct"] == 75
    assert received[2]["type"] == "done"


@pytest.mark.asyncio
async def test_payload_too_large_raises_before_hitting_db(asyncpg_dsn: str) -> None:
    publisher = PgNotificationBus(dsn=asyncpg_dsn)

    with pytest.raises(PayloadTooLarge):
        await publisher.publish("sse:test:big", {"type": "data", "payload": {"x": "A" * 9000}})


@pytest.mark.asyncio
async def test_channel_isolation_different_channels(asyncpg_dsn: str) -> None:
    """Messages on channel A must NOT arrive to a subscriber on channel B."""
    publisher = PgNotificationBus(dsn=asyncpg_dsn)
    subscriber_b = PgNotificationBus(dsn=asyncpg_dsn)

    channel_a = "sse:test:isolation-a"
    channel_b = "sse:test:isolation-b"

    received_on_b: list[dict[str, Any]] = []

    async def _consume_b() -> None:
        async for msg in subscriber_b.subscribe(channel_b, max_messages=1):
            received_on_b.append(msg)

    task = asyncio.create_task(_consume_b())
    await asyncio.sleep(0.05)

    # Publish on A — B subscriber should NOT receive it
    await publisher.publish(channel_a, {"type": "noise", "payload": {}})
    await asyncio.sleep(0.1)

    # Publish on B — B subscriber SHOULD receive it
    await publisher.publish(channel_b, {"type": "signal", "payload": {}})

    await asyncio.wait_for(task, timeout=5.0)

    assert len(received_on_b) == 1
    assert received_on_b[0]["type"] == "signal"
