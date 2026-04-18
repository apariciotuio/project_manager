"""EP-09 — Integration tests: POST /api/v1/search.

Puppet is always the fake in tests (PUPPET_USE_FAKE=true from settings).
"""

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
_SEARCH_URL = "/api/v1/search"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE ownership_history, state_transitions, work_items, "
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


async def _seed(migrated_database) -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)
        user = User.from_google_claims(
            sub="ep09-search", email="ep09search@test.com", name="S", picture=None
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="ep09search@test.com", created_by=user.id)
        ws.slug = "ep09-search"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, ws, token


def _auth(token: str) -> dict[str, str]:
    return {"access_token": token}


@pytest.mark.asyncio
async def test_search_unauthenticated_returns_401(http: AsyncClient, migrated_database) -> None:
    r = await http.post(_SEARCH_URL, json={"q": "auth flow"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_200_with_puppet_source(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_SEARCH_URL, json={"q": "authentication"}, cookies=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert "items" in body["data"]
    assert "took_ms" in body["data"]
    assert "source" in body["data"]
    # FakePuppet returns empty for unknown docs — just verify structure
    assert body["data"]["source"] in ("puppet", "sql_fallback")


@pytest.mark.asyncio
async def test_search_short_query_returns_422(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_SEARCH_URL, json={"q": "x"}, cookies=_auth(token))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_limit_above_100_returns_422(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_SEARCH_URL, json={"q": "hello world", "limit": 101}, cookies=_auth(token))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_search_response_shape(http: AsyncClient, migrated_database) -> None:
    _, _, token = await _seed(migrated_database)
    r = await http.post(_SEARCH_URL, json={"q": "test query"}, cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    assert "items" in data
    assert "took_ms" in data
    assert "source" in data
    assert "total" in data
