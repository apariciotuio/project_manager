"""EP-00 Phase 8 — slowapi in-memory rate limiting on /api/v1/auth/*.

10 req/min per IP. 11th request returns 429 TOO_MANY_REQUESTS with Retry-After.
"""

from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient


@pytest_asyncio.fixture
async def app_with_fresh_limiter(migrated_database):
    """Fresh app per test — slowapi's in-memory backend resets with the app instance.

    Pins the limit to 10/min for deterministic assertions. The conftest wires a
    shared Settings object into get_settings; mutate its auth section so the
    lazy AUTH_LIMIT callable picks up 10/min regardless of the production default.
    """
    original_limit = migrated_database.auth.rate_limit_per_minute
    migrated_database.auth.rate_limit_per_minute = 10

    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    from app.main import create_app

    fastapi_app = create_app()
    # Reset the storage the Limiter uses so the 10/min bucket starts empty for each test.
    limiter = fastapi_app.state.limiter
    limiter.reset()

    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None
    migrated_database.auth.rate_limit_per_minute = original_limit


@pytest_asyncio.fixture
async def http(app_with_fresh_limiter):
    async with AsyncClient(
        transport=ASGITransport(app=app_with_fresh_limiter),
        base_url="http://test",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.0.0.1"},
    ) as client:
        yield client


async def test_auth_google_allows_first_ten_requests(http) -> None:
    for i in range(10):
        resp = await http.get("/api/v1/auth/google")
        assert resp.status_code == 302, f"request #{i + 1} unexpectedly got {resp.status_code}"


async def test_auth_google_blocks_eleventh_request_with_429(http) -> None:
    for _ in range(10):
        resp = await http.get("/api/v1/auth/google")
        assert resp.status_code == 302

    over = await http.get("/api/v1/auth/google")
    assert over.status_code == 429
    body = over.json()
    assert body["error"]["code"] == "TOO_MANY_REQUESTS"
    assert "Retry-After" in over.headers or "retry-after" in {h.lower() for h in over.headers}


async def test_rate_limit_is_per_ip(http, app_with_fresh_limiter) -> None:
    for _ in range(10):
        resp = await http.get("/api/v1/auth/google")
        assert resp.status_code == 302

    # Different IP — separate bucket, should not be limited.
    async with AsyncClient(
        transport=ASGITransport(app=app_with_fresh_limiter),
        base_url="http://test",
        follow_redirects=False,
        headers={"X-Forwarded-For": "10.0.0.2"},
    ) as other_client:
        resp = await other_client.get("/api/v1/auth/google")
        assert resp.status_code == 302


async def test_non_auth_endpoints_not_rate_limited(http) -> None:
    # /api/v1/health (outside /auth/) must tolerate more than 10 req/min.
    for _ in range(15):
        resp = await http.get("/api/v1/health")
        assert resp.status_code == 200
