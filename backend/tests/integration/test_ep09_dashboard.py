"""EP-09 — Integration tests: GET /api/v1/workspaces/dashboard."""
from __future__ import annotations

import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl
from app.main import create_app

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_DASHBOARD_URL = "/api/v1/workspaces/dashboard"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE timeline_events, ownership_history, state_transitions, work_items, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

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
async def http(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed(migrated_database) -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)
        user = User.from_google_claims(sub="ep09-dash", email="ep09dash@test.com", name="D", picture=None)
        await users.upsert(user)
        ws = Workspace.create_from_email(email="ep09dash@test.com", created_by=user.id)
        ws.slug = "ep09-dash"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(workspace_id=ws.id, user_id=user.id, role="admin", is_default=True)
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    token = jwt.encode({
        "sub": str(user.id),
        "email": user.email,
        "workspace_id": str(ws.id),
        "is_superadmin": False,
        "exp": int(time.time()) + 3600,
    })
    return user, ws, token


def _auth(token: str) -> dict[str, str]:
    return {"access_token": token}


@pytest.mark.asyncio
async def test_dashboard_unauthenticated_returns_401(http: AsyncClient, migrated_database) -> None:
    r = await http.get(_DASHBOARD_URL)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_empty_workspace(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.get(_DASHBOARD_URL, cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["work_items"]["total"] == 0
    assert data["work_items"]["by_state"] == {}
    assert data["work_items"]["by_type"] == {}
    assert data["work_items"]["avg_completeness"] == 0.0
    assert data["recent_activity"] == []


@pytest.mark.asyncio
async def test_dashboard_with_work_items(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    # Create 2 work items
    await http.post("/api/v1/work-items", json={"title": "Task A", "type": "task"}, cookies=_auth(token))
    await http.post("/api/v1/work-items", json={"title": "Story B", "type": "story"}, cookies=_auth(token))

    r = await http.get(_DASHBOARD_URL, cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["work_items"]["total"] == 2
    assert "draft" in data["work_items"]["by_state"]
    assert data["work_items"]["by_state"]["draft"] == 2
    assert "task" in data["work_items"]["by_type"]
    assert "story" in data["work_items"]["by_type"]


@pytest.mark.asyncio
async def test_dashboard_response_shape(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.get(_DASHBOARD_URL, cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    # Verify required keys
    assert "work_items" in data
    assert "total" in data["work_items"]
    assert "by_state" in data["work_items"]
    assert "by_type" in data["work_items"]
    assert "avg_completeness" in data["work_items"]
    assert "recent_activity" in data


@pytest.mark.asyncio
async def test_dashboard_cached_second_call(http: AsyncClient, migrated_database) -> None:
    """Second call within TTL returns same data (cache hit). No assertion on timing — just no error."""
    _, _, token = await _seed(migrated_database)
    r1 = await http.get(_DASHBOARD_URL, cookies=_auth(token))
    r2 = await http.get(_DASHBOARD_URL, cookies=_auth(token))
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same data from cache
    assert r1.json()["data"] == r2.json()["data"]
