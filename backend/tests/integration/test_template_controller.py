"""Integration tests for Template endpoints — EP-02 Phase 6.

Tests:
  GET /api/v1/templates
  POST /api/v1/templates
  PATCH /api/v1/templates/{id}
  DELETE /api/v1/templates/{id}
"""

from __future__ import annotations

import time
from uuid import uuid4

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE work_item_drafts, templates, ownership_history, "
                "state_transitions, work_items, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()

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
    ) as client:
        yield client


async def _seed(migrated_database, *, role: str = "admin"):
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-{uuid4().hex[:8]}",
            email=f"u{uuid4().hex[:6]}@test.com",
            name="U",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role=role, is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
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


# ---------------------------------------------------------------------------
# GET /api/v1/templates
# ---------------------------------------------------------------------------


class TestGetTemplates:
    async def test_returns_workspace_template_when_exists(
        self, http: AsyncClient, migrated_database
    ) -> None:
        user, ws, token = await _seed(migrated_database)

        # Create template
        await http.post(
            "/api/v1/templates",
            json={"type": "bug", "name": "Bug Report", "content": "## Summary"},
            cookies={"access_token": token},
        )

        resp = await http.get(
            f"/api/v1/templates?type=bug&workspace_id={ws.id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["type"] == "bug"
        assert body["data"]["name"] == "Bug Report"

    async def test_returns_null_when_no_template(
        self, http: AsyncClient, migrated_database
    ) -> None:
        user, ws, token = await _seed(migrated_database)

        resp = await http.get(
            f"/api/v1/templates?type=bug&workspace_id={ws.id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get(f"/api/v1/templates?type=bug&workspace_id={uuid4()}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/templates
# ---------------------------------------------------------------------------


class TestPostTemplates:
    async def test_admin_creates_template_returns_201(
        self, http: AsyncClient, migrated_database
    ) -> None:
        user, ws, token = await _seed(migrated_database, role="admin")

        resp = await http.post(
            "/api/v1/templates",
            json={"type": "bug", "name": "Bug Report", "content": "## Summary\n\n## Steps"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body["data"]
        assert body["data"]["type"] == "bug"

    async def test_non_admin_gets_403(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")

        resp = await http.post(
            "/api/v1/templates",
            json={"type": "bug", "name": "Bug Report", "content": "## Summary"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 403

    async def test_duplicate_type_returns_409(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        await http.post(
            "/api/v1/templates",
            json={"type": "bug", "name": "Bug", "content": "## Bug"},
            cookies={"access_token": token},
        )
        resp = await http.post(
            "/api/v1/templates",
            json={"type": "bug", "name": "Bug 2", "content": "## Bug 2"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "DUPLICATE_TEMPLATE"

    async def test_content_too_long_returns_422(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        resp = await http.post(
            "/api/v1/templates",
            json={"type": "task", "name": "Task", "content": "x" * 50001},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/templates/{id}
# ---------------------------------------------------------------------------


class TestPatchTemplates:
    async def test_admin_updates_template_returns_200(
        self, http: AsyncClient, migrated_database
    ) -> None:
        user, ws, token = await _seed(migrated_database)

        r = await http.post(
            "/api/v1/templates",
            json={"type": "enhancement", "name": "Enh", "content": "## Goal"},
            cookies={"access_token": token},
        )
        template_id = r.json()["data"]["id"]

        resp = await http.patch(
            f"/api/v1/templates/{template_id}",
            json={"name": "Enhancement Report", "content": "## Updated"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "Enhancement Report"

    async def test_non_admin_gets_403(self, http: AsyncClient, migrated_database) -> None:
        # Create template as admin, then try to update as member
        user_admin, ws, token_admin = await _seed(migrated_database, role="admin")
        r = await http.post(
            "/api/v1/templates",
            json={"type": "task", "name": "Task", "content": "## Task"},
            cookies={"access_token": token_admin},
        )
        template_id = r.json()["data"]["id"]

        # Create member in same workspace
        engine = create_async_engine(migrated_database.database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            users2 = UserRepositoryImpl(session)
            memberships2 = WorkspaceMembershipRepositoryImpl(session)
            user2 = User.from_google_claims(
                sub=f"sub-m{uuid4().hex[:8]}",
                email=f"m{uuid4().hex[:6]}@test.com",
                name="M",
                picture=None,
            )
            await users2.upsert(user2)
            await memberships2.create(
                WorkspaceMembership.create(
                    workspace_id=ws.id, user_id=user2.id, role="member", is_default=True
                )
            )
            await session.commit()
        await engine.dispose()

        jwt = JwtAdapter(
            secret="change-me-in-prod-use-32-chars-or-more-please",
            issuer="wmp",
            audience="wmp-web",
        )
        token_member = jwt.encode(
            {
                "sub": str(user2.id),
                "email": user2.email,
                "workspace_id": str(ws.id),
                "is_superadmin": False,
                "exp": int(time.time()) + 3600,
            }
        )

        resp = await http.patch(
            f"/api/v1/templates/{template_id}",
            json={"content": "## Hacked"},
            cookies={"access_token": token_member},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/v1/templates/{id}
# ---------------------------------------------------------------------------


class TestDeleteTemplates:
    async def test_admin_deletes_template_returns_204(
        self, http: AsyncClient, migrated_database
    ) -> None:
        user, ws, token = await _seed(migrated_database)

        r = await http.post(
            "/api/v1/templates",
            json={"type": "spike", "name": "Spike", "content": "## Goal"},
            cookies={"access_token": token},
        )
        template_id = r.json()["data"]["id"]

        resp = await http.delete(
            f"/api/v1/templates/{template_id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 204
