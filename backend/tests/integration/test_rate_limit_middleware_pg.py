"""Integration tests for RateLimitMiddleware wired to PgRateLimiter.

Uses the real Postgres test container (via migrated_database fixture).
Tests hit a minimal Starlette app with RateLimitMiddleware injected directly,
so no Redis is involved.

Scenarios:
  - Under limit → 200 with rate-limit headers
  - Over limit → 429 with Retry-After + X-RateLimit-* headers
  - DB failure → fail-open (200 + WARNING logged)
"""

from __future__ import annotations

import logging

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.rate_limiting.pg_rate_limiter import (
    PgRateLimiter,
    RateLimitMiddleware,
)


def _build_test_app(
    unauth_limit: int = 5,
    session_factory=None,
) -> Starlette:
    async def handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    base = Starlette(routes=[Route("/ping", handler)])

    factory = session_factory or get_session_factory()

    async def _make_limiter() -> PgRateLimiter:
        async with factory() as session:
            return PgRateLimiter(session)

    middleware = RateLimitMiddleware(
        app=base,
        session_factory=factory,
        unauth_limit=unauth_limit,
        auth_limit=300,
    )
    return middleware  # type: ignore[return-value]


@pytest_asyncio.fixture
async def pg_client(migrated_database):
    """HTTP client backed by a real Postgres session factory (limit=3/min)."""
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    app = _build_test_app(unauth_limit=3)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "10.20.30.40"},
    ) as client:
        yield client

    db_module._engine = None
    db_module._session_factory = None


# ---------------------------------------------------------------------------
# Scenario: under limit → 200 + headers present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_under_limit_returns_200_with_headers(pg_client) -> None:
    resp = await pg_client.get("/ping")

    assert resp.status_code == 200
    assert "x-ratelimit-limit" in resp.headers
    assert "x-ratelimit-remaining" in resp.headers
    assert "x-ratelimit-reset" in resp.headers


@pytest.mark.asyncio
async def test_remaining_decreases_per_request(pg_client) -> None:
    r1 = await pg_client.get("/ping")
    r2 = await pg_client.get("/ping")

    assert r1.status_code == 200
    assert r2.status_code == 200
    rem1 = int(r1.headers["x-ratelimit-remaining"])
    rem2 = int(r2.headers["x-ratelimit-remaining"])
    assert rem2 == rem1 - 1


# ---------------------------------------------------------------------------
# Scenario: over limit → 429 + Retry-After
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_over_limit_returns_429(migrated_database) -> None:
    """Exhaust a 2-request limit, assert next call is 429."""
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    app = _build_test_app(unauth_limit=2)
    # Use a distinct IP so this test's bucket doesn't collide with pg_client fixture
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "99.88.77.66"},
    ) as client:
        for _ in range(2):
            r = await client.get("/ping")
            assert r.status_code == 200

        over = await client.get("/ping")

    assert over.status_code == 429
    body = over.json()
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"

    db_module._engine = None
    db_module._session_factory = None


@pytest.mark.asyncio
async def test_429_includes_retry_after_header(migrated_database) -> None:
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    app = _build_test_app(unauth_limit=1)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Forwarded-For": "55.44.33.22"},
    ) as client:
        await client.get("/ping")
        over = await client.get("/ping")

    assert over.status_code == 429
    assert "retry-after" in over.headers
    assert "x-ratelimit-limit" in over.headers
    assert "x-ratelimit-remaining" in over.headers
    assert "x-ratelimit-reset" in over.headers

    db_module._engine = None
    db_module._session_factory = None


# ---------------------------------------------------------------------------
# Scenario: DB failure → fail-open (200 + WARNING log)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_db_failure_fails_open_with_warning(caplog: pytest.LogCaptureFixture) -> None:
    """When the session factory raises, middleware fails open and logs WARNING."""

    class _BrokenSession:
        async def execute(self, *args, **kwargs):
            raise RuntimeError("simulated DB failure")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class _BrokenFactory:
        def __call__(self):
            return _BrokenSession()

    async def handler(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    base = Starlette(routes=[Route("/ping", handler)])
    middleware = RateLimitMiddleware(
        app=base,
        session_factory=_BrokenFactory(),
        unauth_limit=10,
        auth_limit=300,
    )

    with caplog.at_level(logging.WARNING):
        async with AsyncClient(
            transport=ASGITransport(app=middleware),  # type: ignore[arg-type]
            base_url="http://test",
        ) as client:
            resp = await client.get("/ping")

    assert resp.status_code == 200
    warning_msgs = [r.message for r in caplog.records if r.levelno >= logging.WARNING]
    assert any(
        "rate limit" in m.lower() or "fail" in m.lower() or "db" in m.lower() for m in warning_msgs
    ), f"Expected a warning log, got: {warning_msgs}"
