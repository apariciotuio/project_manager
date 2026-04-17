"""EP-09 — Integration tests: saved searches endpoints.

POST   /api/v1/saved-searches
GET    /api/v1/saved-searches
GET    /api/v1/saved-searches/{id}/run
PATCH  /api/v1/saved-searches/{id}
DELETE /api/v1/saved-searches/{id}
"""
from __future__ import annotations

import time
from uuid import uuid4

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
_BASE = "/api/v1/saved-searches"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE saved_searches, ownership_history, state_transitions, work_items, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    fastapi_app = create_app()
    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _seed(migrated_database, *, sub: str = "ep09-ss", email: str = "ep09ss@test.com", slug: str = "ep09-ss") -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)
        user = User.from_google_claims(sub=sub, email=email, name="SS", picture=None)
        await users.upsert(user)
        ws = Workspace.create_from_email(email=email, created_by=user.id)
        ws.slug = slug
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


# ---------------------------------------------------------------------------
# POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_saved_search_201(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_BASE, json={"name": "my search"}, cookies=_auth(token))
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["name"] == "my search"
    assert data["is_shared"] is False


@pytest.mark.asyncio
async def test_create_unauthenticated_returns_401(http: AsyncClient, migrated_database) -> None:
    r = await http.post(_BASE, json={"name": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_create_empty_name_returns_422(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_BASE, json={"name": "  "}, cookies=_auth(token))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_with_query_params(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(
        _BASE,
        json={"name": "drafts", "query_params": {"state": ["draft"]}},
        cookies=_auth(token),
    )
    assert r.status_code == 201
    assert r.json()["data"]["query_params"] == {"state": ["draft"]}


# ---------------------------------------------------------------------------
# GET list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_returns_own(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    await http.post(_BASE, json={"name": "s1"}, cookies=_auth(token))
    await http.post(_BASE, json={"name": "s2"}, cookies=_auth(token))
    r = await http.get(_BASE, cookies=_auth(token))
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


@pytest.mark.asyncio
async def test_list_unauthenticated_returns_401(http: AsyncClient, migrated_database) -> None:
    r = await http.get(_BASE)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_name(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    create_r = await http.post(_BASE, json={"name": "old"}, cookies=_auth(token))
    ss_id = create_r.json()["data"]["id"]

    r = await http.patch(f"{_BASE}/{ss_id}", json={"name": "new"}, cookies=_auth(token))
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "new"


@pytest.mark.asyncio
async def test_patch_is_shared(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    create_r = await http.post(_BASE, json={"name": "shareable"}, cookies=_auth(token))
    ss_id = create_r.json()["data"]["id"]

    r = await http.patch(f"{_BASE}/{ss_id}", json={"is_shared": True}, cookies=_auth(token))
    assert r.status_code == 200
    assert r.json()["data"]["is_shared"] is True


@pytest.mark.asyncio
async def test_patch_not_owner_returns_403(http: AsyncClient, migrated_database) -> None:
    _, ws, token1 = await _seed(migrated_database)
    create_r = await http.post(_BASE, json={"name": "owner's search"}, cookies=_auth(token1))
    ss_id = create_r.json()["data"]["id"]

    # Seed a second user in the same workspace
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)
        user2 = User.from_google_claims(sub="ep09-ss-2", email="ep09ss2@test.com", name="U2", picture=None)
        await users.upsert(user2)
        await memberships.create(
            WorkspaceMembership.create(workspace_id=ws.id, user_id=user2.id, role="member", is_default=True)
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    token2 = jwt.encode({"sub": str(user2.id), "email": user2.email, "workspace_id": str(ws.id), "is_superadmin": False, "exp": int(time.time()) + 3600})

    r = await http.patch(f"{_BASE}/{ss_id}", json={"name": "hijack"}, cookies=_auth(token2))
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_patch_nonexistent_returns_404(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.patch(f"{_BASE}/{uuid4()}", json={"name": "x"}, cookies=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_own_returns_204(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    create_r = await http.post(_BASE, json={"name": "to delete"}, cookies=_auth(token))
    ss_id = create_r.json()["data"]["id"]

    r = await http.delete(f"{_BASE}/{ss_id}", cookies=_auth(token))
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_nonexistent_returns_404(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.delete(f"{_BASE}/{uuid4()}", cookies=_auth(token))
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_saved_search(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    # Create a work item first
    await http.post("/api/v1/work-items", json={"title": "Draft item", "type": "task"}, cookies=_auth(token))

    # Create saved search for drafts
    create_r = await http.post(
        _BASE,
        json={"name": "drafts", "query_params": {"state": ["draft"]}},
        cookies=_auth(token),
    )
    ss_id = create_r.json()["data"]["id"]

    r = await http.get(f"{_BASE}/{ss_id}/run", cookies=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body["data"]
    assert len(body["data"]["items"]) >= 1


@pytest.mark.asyncio
async def test_run_not_found_returns_404(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.get(f"{_BASE}/{uuid4()}/run", cookies=_auth(token))
    assert r.status_code == 404
