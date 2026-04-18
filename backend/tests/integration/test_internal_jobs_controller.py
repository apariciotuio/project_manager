"""Integration tests for internal_jobs_controller.

POST /api/v1/internal/jobs/{name}/run

Cases:
  - Non-superadmin token → 403
  - Superadmin + unknown job name → 404
  - Superadmin + known job name → 200, job function invoked
  - Rate limit (6th call within 1 minute) → 429 — DEFERRED (see comment below)

Rate-limit note: the `auth_limiter` is a module-level singleton Limiter.
Resetting it between tests requires access to the private in-memory storage
dict, which varies by slowapi version and is not stable. Hammering 6 requests
inside a minute also makes the test order-dependent unless the limiter is truly
isolated per test. Deferred — use a fresh app instance with limiter.reset() as
done in test_rate_limiting.py if needed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_BASE_URL = "/api/v1/internal/jobs"
_CSRF_TOKEN = "test-csrf-token-fixed"  # any stable value — double-submit pattern
_CSRF_HEADERS = {"X-CSRF-Token": _CSRF_TOKEN}
_CSRF_COOKIES = {"csrf_token": _CSRF_TOKEN}


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(*, is_superadmin: bool, workspace_id: str | None = None) -> str:
    adapter = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid4()),
        "email": f"{uuid4().hex[:8]}@tuio.com",
        "is_superadmin": is_superadmin,
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
    }
    if workspace_id is not None:
        payload["workspace_id"] = workspace_id
    return adapter.encode(payload)


def _superadmin_token() -> str:
    return _make_token(is_superadmin=True)


def _regular_user_token() -> str:
    return _make_token(is_superadmin=False, workspace_id=str(uuid4()))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):  # noqa: ARG001 — pulls in settings override + runs migrations
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    from app.main import create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache

    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
        headers={"X-Forwarded-For": "192.0.2.1"},  # fixed IP so rate-limit bucket is deterministic
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_job_without_auth_returns_401(http: AsyncClient) -> None:
    """No access_token cookie → 401 MISSING_TOKEN (CSRF passes, auth fails)."""
    resp = await http.post(
        f"{_BASE_URL}/cleanup_expired_sessions/run",
        headers=_CSRF_HEADERS,
        cookies=_CSRF_COOKIES,
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_run_job_non_superadmin_returns_403(http: AsyncClient) -> None:
    """Valid token but is_superadmin=False → 403 SUPERADMIN_REQUIRED."""
    token = _regular_user_token()
    resp = await http.post(
        f"{_BASE_URL}/cleanup_expired_sessions/run",
        headers=_CSRF_HEADERS,
        cookies={"access_token": token, **_CSRF_COOKIES},
    )
    assert resp.status_code == 403
    body = resp.json()
    # error_middleware passes exc.detail directly when it contains "error" key
    assert body["error"]["code"] == "SUPERADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_run_job_superadmin_unknown_job_returns_404(http: AsyncClient) -> None:
    """Superadmin + job name not in registry → 404 JOB_NOT_FOUND."""
    token = _superadmin_token()
    resp = await http.post(
        f"{_BASE_URL}/does_not_exist/run",
        headers=_CSRF_HEADERS,
        cookies={"access_token": token, **_CSRF_COOKIES},
    )
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "JOB_NOT_FOUND"
    # available list must be non-empty
    assert len(body["error"]["details"]["available"]) > 0


@pytest.mark.asyncio
async def test_run_job_superadmin_known_job_invokes_function(
    http: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Superadmin + known job name → 200, job function is called exactly once."""
    import app.presentation.controllers.internal_jobs_controller as ctrl_mod

    called: list[str] = []

    async def _fake_job() -> dict:
        called.append("invoked")
        return {"deleted": 0}

    # Inject directly into the registry so no real DB job runs.
    original = ctrl_mod._JOB_REGISTRY.get("cleanup_expired_oauth_states")
    ctrl_mod._JOB_REGISTRY["cleanup_expired_oauth_states"] = _fake_job

    try:
        token = _superadmin_token()
        resp = await http.post(
            f"{_BASE_URL}/cleanup_expired_oauth_states/run",
            headers=_CSRF_HEADERS,
            cookies={"access_token": token, **_CSRF_COOKIES},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["data"]["job"] == "cleanup_expired_oauth_states"
        assert called == ["invoked"]
    finally:
        if original is not None:
            ctrl_mod._JOB_REGISTRY["cleanup_expired_oauth_states"] = original
        else:
            del ctrl_mod._JOB_REGISTRY["cleanup_expired_oauth_states"]


@pytest.mark.asyncio
async def test_run_job_returns_job_result_in_response(
    http: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Job result dict is nested inside data.result."""
    import app.presentation.controllers.internal_jobs_controller as ctrl_mod

    async def _fake_job() -> dict:
        return {"count": 42}

    original = ctrl_mod._JOB_REGISTRY.get("expire_work_item_drafts")
    ctrl_mod._JOB_REGISTRY["expire_work_item_drafts"] = _fake_job

    try:
        token = _superadmin_token()
        resp = await http.post(
            f"{_BASE_URL}/expire_work_item_drafts/run",
            headers=_CSRF_HEADERS,
            cookies={"access_token": token, **_CSRF_COOKIES},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["result"] == {"count": 42}
    finally:
        if original is not None:
            ctrl_mod._JOB_REGISTRY["expire_work_item_drafts"] = original
        else:
            del ctrl_mod._JOB_REGISTRY["expire_work_item_drafts"]


@pytest.mark.asyncio
async def test_run_job_wraps_job_exception_in_500(
    http: AsyncClient,
) -> None:
    """When the job function raises, response is 500 JOB_FAILED."""
    import app.presentation.controllers.internal_jobs_controller as ctrl_mod

    async def _exploding_job() -> dict:
        raise RuntimeError("disk full")

    original = ctrl_mod._JOB_REGISTRY.get("sweep_notifications")
    ctrl_mod._JOB_REGISTRY["sweep_notifications"] = _exploding_job

    try:
        token = _superadmin_token()
        resp = await http.post(
            f"{_BASE_URL}/sweep_notifications/run",
            headers=_CSRF_HEADERS,
            cookies={"access_token": token, **_CSRF_COOKIES},
        )
        assert resp.status_code == 500
        body = resp.json()
        assert body["error"]["code"] == "JOB_FAILED"
    finally:
        if original is not None:
            ctrl_mod._JOB_REGISTRY["sweep_notifications"] = original
        else:
            del ctrl_mod._JOB_REGISTRY["sweep_notifications"]


# ---------------------------------------------------------------------------
# DEFERRED: rate-limit 429 test
# ---------------------------------------------------------------------------
# Reason: auth_limiter is a module-level singleton (slowapi Limiter). Its
# in-memory storage is shared across all requests in the same process.
# Reliably resetting it per-test requires calling limiter.reset() on the
# Limiter attached to app.state, which requires a dedicated fresh app instance
# with rate_limit_per_minute=5 pinned in AuthSettings (same pattern as
# test_rate_limiting.py). Adding it here would duplicate that fixture without
# meaningful new signal — the existing test_rate_limiting.py already covers
# the slowapi 429 path for /auth/* routes. Track as follow-up if the
# /internal/jobs/* rate limit needs independent verification.
