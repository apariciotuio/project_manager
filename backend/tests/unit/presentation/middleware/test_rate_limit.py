"""Tests for RateLimitMiddleware backed by PgRateLimiter.

Uses a fake session factory (in-memory dict) injected via constructor —
no real DB, no Redis.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from starlette.testclient import TestClient

from app.infrastructure.rate_limiting.pg_rate_limiter import (
    RateLimitMiddleware,
    RateLimitResult,
)


# ---------------------------------------------------------------------------
# Fake session + factory
# ---------------------------------------------------------------------------


class _FakeRow:
    def __init__(self, count: int, window_start_minute: Any) -> None:
        from datetime import datetime, timezone

        self.count = count
        self.window_start_minute = window_start_minute or datetime(
            2026, 4, 18, 10, 0, tzinfo=timezone.utc
        )


class _FakeResult:
    def __init__(self, row: _FakeRow | None) -> None:
        self._row = row

    def fetchone(self) -> _FakeRow | None:
        return self._row


class FakeSession:
    """In-memory session that simulates the upsert per identifier."""

    def __init__(self, buckets: dict[str, int], raise_exc: bool = False) -> None:
        self._buckets = buckets
        self._raise = raise_exc

    async def execute(self, statement: Any, params: dict | None = None) -> _FakeResult:
        if self._raise:
            raise RuntimeError("DB unavailable")
        from datetime import datetime, timezone

        identifier = (params or {}).get("identifier", "")
        self._buckets[identifier] = self._buckets.get(identifier, 0) + 1
        return _FakeResult(
            _FakeRow(
                count=self._buckets[identifier],
                window_start_minute=datetime(2026, 4, 18, 10, 0, tzinfo=timezone.utc),
            )
        )

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


class FakeSessionFactory:
    """Returns the same FakeSession on every call (shared bucket store)."""

    def __init__(self, raise_exc: bool = False) -> None:
        self._buckets: dict[str, int] = {}
        self._raise = raise_exc

    def __call__(self) -> FakeSession:
        return FakeSession(self._buckets, raise_exc=self._raise)

    def reset(self) -> None:
        self._buckets.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_app(
    factory: FakeSessionFactory,
    unauth_limit: int = 10,
    auth_limit: int = 300,
    get_user_id=None,
) -> Any:
    async def handler(request: Request) -> Response:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/test", handler), Route("/api/resource", handler)])

    return RateLimitMiddleware(
        app=app,
        session_factory=factory,
        unauth_limit=unauth_limit,
        auth_limit=auth_limit,
        get_user_id=get_user_id or (lambda _r: None),
    )


# ---------------------------------------------------------------------------
# Tests — unauthenticated rate limiting
# ---------------------------------------------------------------------------


def test_unauth_allows_requests_under_limit() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=3)
    client = TestClient(app)  # type: ignore[arg-type]

    for _ in range(3):
        resp = client.get("/test", headers={"X-Forwarded-For": "1.2.3.4"})
        assert resp.status_code == 200


def test_unauth_returns_429_on_limit_exceeded() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=3)
    client = TestClient(app)  # type: ignore[arg-type]

    for _ in range(3):
        client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})

    resp = client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})
    assert resp.status_code == 429


def test_unauth_429_includes_retry_after_header() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=2)
    client = TestClient(app)  # type: ignore[arg-type]

    client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
    client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})
    resp = client.get("/test", headers={"X-Forwarded-For": "5.5.5.5"})

    assert resp.status_code == 429
    assert "retry-after" in resp.headers


# ---------------------------------------------------------------------------
# Tests — authenticated rate limiting
# ---------------------------------------------------------------------------


def test_auth_limit_is_higher_than_unauth() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=2, auth_limit=10, get_user_id=lambda _r: "user-abc-123")
    client = TestClient(app)  # type: ignore[arg-type]

    for _ in range(10):
        resp = client.get("/test")
        assert resp.status_code == 200

    resp = client.get("/test")
    assert resp.status_code == 429


def test_auth_uses_user_id_not_ip_as_key() -> None:
    """Two different IPs for the same user share a rate limit bucket."""
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=100, auth_limit=3, get_user_id=lambda _r: "shared-user")
    client = TestClient(app)  # type: ignore[arg-type]

    for ip in ["1.1.1.1", "2.2.2.2", "3.3.3.3"]:
        client.get("/test", headers={"X-Forwarded-For": ip})

    resp = client.get("/test", headers={"X-Forwarded-For": "4.4.4.4"})
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Tests — rate limit headers always present
# ---------------------------------------------------------------------------


def test_rate_limit_headers_present_on_successful_request() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=10)
    client = TestClient(app)  # type: ignore[arg-type]

    resp = client.get("/test", headers={"X-Forwarded-For": "9.9.9.9"})

    assert resp.status_code == 200
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert "x-ratelimit-reset" in resp.headers


def test_rate_limit_remaining_decreases_with_each_request() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=10)
    client = TestClient(app)  # type: ignore[arg-type]

    resp1 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})
    remaining1 = int(resp1.headers["x-ratelimit-remaining"])

    resp2 = client.get("/test", headers={"X-Forwarded-For": "7.7.7.7"})
    remaining2 = int(resp2.headers["x-ratelimit-remaining"])

    assert remaining2 == remaining1 - 1


# ---------------------------------------------------------------------------
# Tests — DB unavailable (fail-open)
# ---------------------------------------------------------------------------


def test_db_unavailable_passes_request_through(caplog: pytest.LogCaptureFixture) -> None:
    factory = FakeSessionFactory(raise_exc=True)
    app = _build_app(factory, unauth_limit=10)
    client = TestClient(app)  # type: ignore[arg-type]

    with caplog.at_level(logging.WARNING):
        resp = client.get("/test")

    assert resp.status_code == 200
    warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "rate limit" in m.lower() or "db" in m.lower() or "unavailable" in m.lower()
        for m in warning_msgs
    )


def test_db_unavailable_no_5xx_returned() -> None:
    factory = FakeSessionFactory(raise_exc=True)
    app = _build_app(factory, unauth_limit=10)
    client = TestClient(app)  # type: ignore[arg-type]

    resp = client.get("/test")
    assert resp.status_code < 500


# ---------------------------------------------------------------------------
# Tests — 429 response body format
# ---------------------------------------------------------------------------


def test_429_response_has_error_envelope() -> None:
    factory = FakeSessionFactory()
    app = _build_app(factory, unauth_limit=1)
    client = TestClient(app)  # type: ignore[arg-type]

    client.get("/test", headers={"X-Forwarded-For": "8.8.8.8"})
    resp = client.get("/test", headers={"X-Forwarded-For": "8.8.8.8"})

    assert resp.status_code == 429
    body = resp.json()
    assert "error" in body
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"
