"""Postgres sliding-window rate limiter + ASGI middleware.

Strategy: single atomic upsert per check.  Each (identifier, minute) pair maps
to one row in `rate_limit_buckets`.  The count is incremented inside a
DO UPDATE so the whole operation is one round-trip with no race conditions.

Fail-open on DB error — logs WARNING and allows the request through to preserve
availability.

RateLimitMiddleware uses ``session_factory`` (an ``async_sessionmaker``) for
Postgres-backed rate limiting.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone, UTC
from typing import Any, Protocol

import sqlalchemy as sa
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_UPSERT_SQL = sa.text(
    """
    INSERT INTO rate_limit_buckets (identifier, window_start_minute)
    VALUES (:identifier, date_trunc('minute', NOW()))
    ON CONFLICT (identifier, window_start_minute)
    DO UPDATE SET count = rate_limit_buckets.count + 1
    RETURNING count, window_start_minute
    """
)


# ---------------------------------------------------------------------------
# Public dataclass — canonical definition (used by both limiter and middleware)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    count: int
    reset_at: int  # UTC epoch second

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)


# ---------------------------------------------------------------------------
# Protocol for AsyncSession duck-typing
# ---------------------------------------------------------------------------


class _AsyncSessionProto(Protocol):
    async def execute(
        self, statement: sa.TextClause, params: dict | None = None
    ) -> sa.engine.Result: ...


class _SessionFactoryProto(Protocol):
    def __call__(self) -> Any: ...


# ---------------------------------------------------------------------------
# PgRateLimiter
# ---------------------------------------------------------------------------


class PgRateLimiter:
    """Sliding-window rate limiter backed by Postgres ``rate_limit_buckets``."""

    def __init__(self, session: _AsyncSessionProto) -> None:
        self._session = session

    async def check(self, identifier: str, limit: int) -> RateLimitResult:
        """Increment the per-minute bucket and return whether the request is allowed.

        Returns:
            RateLimitResult with allowed, limit, count, and reset_at (UTC epoch second).

        On any DB error: logs WARNING and returns an allow-all result (fail-open).
        """
        try:
            result = await self._session.execute(
                _UPSERT_SQL,
                {"identifier": identifier},
            )
            row = result.fetchone()
            if row is None:
                # Should never happen with RETURNING, but guard anyway.
                raise RuntimeError("RETURNING clause returned no row")

            count: int = row.count
            window_start: datetime = row.window_start_minute
            # Reset is the start of the *next* minute.
            if window_start.tzinfo is None:
                window_start = window_start.replace(tzinfo=UTC)
            reset_at = int(window_start.timestamp()) + 60

            return RateLimitResult(
                allowed=count <= limit,
                limit=limit,
                count=count,
                reset_at=reset_at,
            )
        except Exception as exc:
            logger.warning(
                "pg_rate_limiter: DB error — failing open: %s",
                exc,
                exc_info=True,
            )
            now_epoch = int(datetime.now(tz=UTC).timestamp())
            window_minute = now_epoch // 60
            return RateLimitResult(
                allowed=True,
                limit=limit,
                count=0,
                reset_at=(window_minute + 1) * 60,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host
    return "unknown"


# ---------------------------------------------------------------------------
# RateLimitMiddleware
# ---------------------------------------------------------------------------


class RateLimitMiddleware:
    """ASGI middleware — pure ASGI to avoid BaseHTTPMiddleware streaming overhead.

    Constructor:
        session_factory — async_sessionmaker[AsyncSession] (or any callable
                          returning an async context manager that yields a session
                          with an ``execute`` method).
        unauth_limit    — requests/min for unauthenticated identifiers (by IP).
        auth_limit      — requests/min for authenticated identifiers (by user_id).
        get_user_id     — optional callable(Request) → str | None.  Return None
                          to use IP-based bucketing.
        exempt_paths    — optional set[str] of paths to exempt from rate limiting
                          (exact match on request path).
    """

    def __init__(
        self,
        app: ASGIApp,
        session_factory: _SessionFactoryProto,
        unauth_limit: int = 10,
        auth_limit: int = 300,
        get_user_id: Callable[[Request], str | None] | None = None,
        exempt_paths: set[str] | None = None,
    ) -> None:
        self._app = app
        self._session_factory = session_factory
        self._unauth_limit = unauth_limit
        self._auth_limit = auth_limit
        self._get_user_id = get_user_id or (lambda _r: None)
        self._exempt_paths = exempt_paths or set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)
        path = scope.get("path", "")

        # Check if this path is exempt from rate limiting
        if path in self._exempt_paths:
            await self._app(scope, receive, send)
            return

        try:
            user_id = self._get_user_id(request)
            if user_id:
                identifier = f"user:{user_id}"
                limit = self._auth_limit
            else:
                identifier = f"ip:{_client_ip(request)}"
                limit = self._unauth_limit

            async with self._session_factory() as session:
                limiter = PgRateLimiter(session)
                result = await limiter.check(identifier, limit)
                await session.commit()
        except Exception as exc:
            logger.warning("rate limit check failed — DB unavailable: %s", exc)
            await self._app(scope, receive, send)
            return

        if not result.allowed:
            retry_after = result.reset_at - int(time.time())
            logger.warning(
                "rate limit exceeded",
                extra={
                    "identifier": identifier,
                    "path": scope.get("path", ""),
                    "request_count": result.count,
                    "limit": result.limit,
                    "window": "1m",
                },
            )
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "TOO_MANY_REQUESTS",
                        "message": "Rate limit exceeded. Try again later.",
                        "details": {"limit": result.limit, "window": "1 minute"},
                    }
                },
                headers={
                    "Retry-After": str(max(1, retry_after)),
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_at),
                },
            )
            await response(scope, receive, send)
            return

        # Allowed — call next and inject headers into the response
        _headers_to_inject = {
            "x-ratelimit-limit": str(result.limit),
            "x-ratelimit-remaining": str(result.remaining),
            "x-ratelimit-reset": str(result.reset_at),
        }

        async def _send_with_headers(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                for k, v in _headers_to_inject.items():
                    headers.append((k.encode(), v.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self._app(scope, receive, _send_with_headers)
