"""Integration tests for GET /api/v1/internal/jobs/ — list_jobs endpoint.

The run endpoint (POST /{name}/run) is covered in test_internal_jobs_controller.py.
This file covers the list endpoint which had zero coverage.

Cases:
  - 401 when unauthenticated
  - 403 when non-superadmin
  - 200 returns sorted list of job names for superadmin
  - Response shape: { data: { jobs: [...] }, message: "ok" }
  - All expected job names present in the list
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_BASE_URL = "/api/v1/internal/jobs"
_CSRF_TOKEN = "test-csrf-list-fixed"
_CSRF_HEADERS = {"X-CSRF-Token": _CSRF_TOKEN}
_CSRF_COOKIES = {"csrf_token": _CSRF_TOKEN}

_EXPECTED_JOBS = frozenset(
    {
        "cleanup_expired_sessions",
        "cleanup_expired_oauth_states",
        "expire_work_item_drafts",
        "sweep_notifications",
        "drain_puppet_outbox",
        "process_puppet_ingest",
    }
)


def _make_token(*, is_superadmin: bool, workspace_id: str | None = None) -> str:
    adapter = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    now = datetime.now(timezone.utc)
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


@pytest_asyncio.fixture
async def app(migrated_database):  # noqa: ARG001
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
        headers={"X-Forwarded-For": "192.0.2.2"},
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_jobs_unauthenticated_returns_401(http: AsyncClient) -> None:
    """No auth cookie → 401."""
    resp = await http.get(f"{_BASE_URL}/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_jobs_non_superadmin_returns_403(http: AsyncClient) -> None:
    """Regular user token → 403 SUPERADMIN_REQUIRED."""
    token = _make_token(is_superadmin=False, workspace_id=str(uuid4()))
    resp = await http.get(f"{_BASE_URL}/", cookies={"access_token": token})
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"]["code"] == "SUPERADMIN_REQUIRED"


@pytest.mark.asyncio
async def test_list_jobs_superadmin_returns_200_with_jobs(http: AsyncClient) -> None:
    """Superadmin → 200 with sorted list of job names."""
    token = _make_token(is_superadmin=True)
    resp = await http.get(f"{_BASE_URL}/", cookies={"access_token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "ok"
    jobs = body["data"]["jobs"]
    assert isinstance(jobs, list)
    assert len(jobs) > 0


@pytest.mark.asyncio
async def test_list_jobs_response_contains_all_expected_job_names(
    http: AsyncClient,
) -> None:
    """All six registered job names must be present."""
    token = _make_token(is_superadmin=True)
    resp = await http.get(f"{_BASE_URL}/", cookies={"access_token": token})
    assert resp.status_code == 200
    jobs = set(resp.json()["data"]["jobs"])
    assert _EXPECTED_JOBS.issubset(jobs), f"Missing jobs: {_EXPECTED_JOBS - jobs}"


@pytest.mark.asyncio
async def test_list_jobs_response_is_sorted(http: AsyncClient) -> None:
    """Job list must be in alphabetical order (sorted() in controller)."""
    token = _make_token(is_superadmin=True)
    resp = await http.get(f"{_BASE_URL}/", cookies={"access_token": token})
    jobs = resp.json()["data"]["jobs"]
    assert jobs == sorted(jobs)
