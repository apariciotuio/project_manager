"""Tests for RateLimitMiddleware — RED phase.

Uses a fake Redis (in-memory dict) injected via constructor to avoid live Redis.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.infrastructure.rate_limiting.redis_rate_limiter import (
    RateLimitMiddleware,
    RateLimitResult,
    RedisRateLimiter,
)


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------


class FakeRedis:
    """Minimal in-memory fake for INCR + EXPIRE + TTL commands."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}
        self._ttls: dict[str, int] = {}
        self.unavailable: bool = False

    async def incr(self, key: str) -> int:
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> None:
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        self._ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        if self.unavailable:
            raise ConnectionError("redis unavailable")
        return self._ttls.get(key, -2)

    def reset(self) -> None:
        self._store.clear()
        self._ttls.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    fake_redis: FakeRedis,
    unauth_limit: int = 10,
    auth_limit: int = 300,
    authenticated_user_id: str | None = None,
) -> Starlette:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler), Route("/api/resource", handler)])

    def _get_user_id(req: Request) -> str | None:
        # Simulate auth middleware having set request.state.user_id
        return getattr(req.state, "user_id", None)

    middleware = RateLimitMiddleware(
        app=app,
        redis=fake_redis,  # type: ignore[arg-type]
        unauth_limit=unauth_limit,
        auth_limit=auth_limit,
        get_user_id=_get_user_id,
    )
    # Wrap in new Starlette so TestClient can inject state before request
    if authenticated_user_id is not None:

        class _InjectUserMiddleware:
            def __init__(self, inner: Any) -> None:
                self._inner = inner

            async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
                if scope["type"] == "http":
                    from starlette.datastructures import State

                    scope.setdefault("state", {})
                scope["state"]["user_id"] = authenticated_user_id
                await self._inner(scope, receive, send)

        return _InjectUserMiddleware(middleware)  # type: ignore[return-value]

    return middleware  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests — unauthenticated rate limiting
# ---------------------------------------------------------------------------


def test_unauth_allows_requests_under_limit(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeRedis()
    app = _build_app(fake, unauth_limit=3)
    client = TestClient(app)

    for _ in range(3):
        resp = client.get("/test", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200


def test_unauth_returns_429_on_limit_exceeded(caplog: pytest.LogCaptureFixture) -> None:
    fake = FakeRedis()
    app = _build_app(fake, unauth_limit=3)
    client = TestClient(app)

    for i in range(3):
        client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})

    resp = client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})
    assert resp.status_code == 429


def test_unauth_429_includes_retry_after_header() -> None:
    fake = FakeRedis()
    app = _build_app(fake, unauth_limit=2)
    client = TestClient(app)

    client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
    client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
    resp = client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})

    assert resp.status_code == 429
    assert "retry-after" in resp.headers


# ---------------------------------------------------------------------------
# Tests — authenticated rate limiting
# ---------------------------------------------------------------------------


def test_auth_limit_is_higher_than_unauth() -> None:
    """Authenticated requests use auth_limit, not unauth_limit."""
    fake = FakeRedis()

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])

    def _get_user_id(req: Request) -> str | None:
        return "user-abc-123"

    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=2,
        auth_limit=10,
        get_user_id=_get_user_id,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]

    # 10 requests — should all succeed (auth limit = 10)
    for _ in range(10):
        resp = client.get("/test")
        assert resp.status_code == 200

    # 11th should fail
    resp = client.get("/test")
    assert resp.status_code == 429


def test_auth_uses_user_id_not_ip_as_key() -> None:
    """Two different IPs for the same user share a rate limit bucket."""
    fake = FakeRedis()

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])

    def _get_user_id(req: Request) -> str | None:
        return "shared-user"

    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=100,
        auth_limit=3,
        get_user_id=_get_user_id,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]

    # 3 requests from different IPs
    for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
        client.get("/test", headers={"X-Forwarded-For": ip})

    # 4th should be 429 (shared bucket by user_id)
    resp = client.get("/test", headers={"X-Forwarded-For": "4.4.4.4"})
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Tests — rate limit headers always present
# ---------------------------------------------------------------------------


def test_rate_limit_headers_present_on_successful_request() -> None:
    fake = FakeRedis()

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=10,
        auth_limit=300,
        get_user_id=lambda r: None,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]
    resp = client.get("/test", headers={"X-Forwarded-For": "9.9.9.9"})

    assert resp.status_code == 200
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert "x-ratelimit-reset" in resp.headers


def test_rate_limit_remaining_decreases_with_each_request() -> None:
    fake = FakeRedis()

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=10,
        auth_limit=300,
        get_user_id=lambda r: None,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]

    resp1 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})
    remaining1 = int(resp1.headers["x-ratelimit-remaining"])

    resp2 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})
    remaining2 = int(resp2.headers["x-ratelimit-remaining"])

    assert remaining2 == remaining1 - 1


# ---------------------------------------------------------------------------
# Tests — Redis unavailable (fail-open)
# ---------------------------------------------------------------------------


def test_redis_unavailable_passes_request_through(caplog: pytest.LogCaptureFixture) -> None:
    """When Redis is down, rate limiter fails open and logs a WARNING."""
    import logging

    fake = FakeRedis()
    fake.unavailable = True

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=10,
        auth_limit=300,
        get_user_id=lambda r: None,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]

    with caplog.at_level(
        logging.WARNING, logger="app.infrastructure.rate_limiting.redis_rate_limiter"
    ):
        resp = client.get("/test")

    assert resp.status_code == 200
    warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("rate limit" in m.lower() or "redis" in m.lower() for m in warning_msgs)


def test_redis_unavailable_no_5xx_returned() -> None:
    fake = FakeRedis()
    fake.unavailable = True

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=10,
        auth_limit=300,
        get_user_id=lambda r: None,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]
    resp = client.get("/test")
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Tests — 429 response body format
# ---------------------------------------------------------------------------


def test_429_response_has_error_envelope() -> None:
    fake = FakeRedis()

    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler)])
    middleware = RateLimitMiddleware(
        app=app,
        redis=fake,  # type: ignore[arg-type]
        unauth_limit=1,
        auth_limit=300,
        get_user_id=lambda r: None,
    )
    client = TestClient(middleware)  # type: ignore[arg-type]

    client.get("/test", headers={"X-Forwarded-For": "8.8.8.8"})
    resp = client.get("/test", headers={"X-Forwarded-For": "8.8.8.8"})

    assert resp.status_code == 429
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"
