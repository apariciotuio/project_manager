"""Redis sliding-window rate limiter middleware.

Strategy: per-minute window keyed by `ratelimit:{identifier}:{window_minute}`.
  - Unauthenticated: keyed by client IP, limit = unauth_limit/min
  - Authenticated: keyed by user_id, limit = auth_limit/min

Fail-open on Redis errors — logs WARNING, allows the request through.

Headers added to every response:
  X-RateLimit-Limit     — effective limit for this identifier
  X-RateLimit-Remaining — requests left in the current window (>=0)
  X-RateLimit-Reset     — UTC epoch second when the window resets
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class _RedisProto(Protocol):
    """Minimal Redis interface required by this module."""

    async def incr(self, key: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> None: ...
    async def ttl(self, key: str) -> int: ...


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    limit: int
    count: int
    reset_at: int  # UTC epoch second

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.count)


class RedisRateLimiter:
    """Stateless sliding-window counter backed by Redis INCR+EXPIRE."""

    def __init__(self, redis: _RedisProto) -> None:
        self._redis = redis

    async def check(self, identifier: str, limit: int) -> RateLimitResult:
        now = int(time.time())
        window_minute = now // 60
        reset_at = (window_minute + 1) * 60
        key = f"ratelimit:{identifier}:{window_minute}"

        count = await self._redis.incr(key)
        if count == 1:
            # First request in this window — set expiry (70s to cover clock skew)
            await self._redis.expire(key, 70)

        return RateLimitResult(
            allowed=count <= limit,
            limit=limit,
            count=count,
            reset_at=reset_at,
        )


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitMiddleware:
    """ASGI middleware — pure ASGI to avoid BaseHTTPMiddleware streaming overhead."""

    def __init__(
        self,
        app: ASGIApp,
        redis: _RedisProto,
        unauth_limit: int = 10,
        auth_limit: int = 300,
        get_user_id: Callable[[Request], str | None] | None = None,
    ) -> None:
        self._app = app
        self._limiter = RedisRateLimiter(redis)
        self._unauth_limit = unauth_limit
        self._auth_limit = auth_limit
        self._get_user_id = get_user_id or (lambda _r: None)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)

        try:
            user_id = self._get_user_id(request)
            if user_id:
                identifier = f"user:{user_id}"
                limit = self._auth_limit
            else:
                identifier = f"ip:{_client_ip(request)}"
                limit = self._unauth_limit

            result = await self._limiter.check(identifier, limit)
        except Exception as exc:
            logger.warning("rate limit check failed — Redis unavailable: %s", exc)
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
