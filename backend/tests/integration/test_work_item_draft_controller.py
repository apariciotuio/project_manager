"""Integration tests for WorkItemDraft and WorkItem draft endpoints — EP-02 Phase 6.

Tests:
  POST /api/v1/work-item-drafts
  GET /api/v1/work-item-drafts
  DELETE /api/v1/work-item-drafts/{id}
  PATCH /api/v1/work-items/{id}/draft
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

    fastapi_app = _create_app()
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
# POST /api/v1/work-item-drafts
# ---------------------------------------------------------------------------


class TestPostWorkItemDrafts:
    async def test_create_draft_returns_200(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        resp = await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {"title": "hello"}, "local_version": 0},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "draft_id" in body["data"]
        assert body["data"]["local_version"] == 1

    async def test_conflict_returns_409(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        # First upsert → version 1
        await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {"v": 1}, "local_version": 0},
            cookies={"access_token": token},
        )
        # Advance to version 2
        await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {"v": 2}, "local_version": 1},
            cookies={"access_token": token},
        )
        # Stale client at version 1
        resp = await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {"v": "stale"}, "local_version": 1},
            cookies={"access_token": token},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"]["code"] == "DRAFT_VERSION_CONFLICT"
        assert body["error"]["details"]["server_version"] == 2

    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(uuid4()), "data": {}, "local_version": 0},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/work-item-drafts
# ---------------------------------------------------------------------------


class TestGetWorkItemDrafts:
    async def test_returns_draft_when_exists(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {"title": "my draft"}, "local_version": 0},
            cookies={"access_token": token},
        )

        resp = await http.get(
            f"/api/v1/work-item-drafts?workspace_id={ws.id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] is not None
        assert body["data"]["data"]["title"] == "my draft"

    async def test_returns_null_when_no_draft(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        resp = await http.get(
            f"/api/v1/work-item-drafts?workspace_id={ws.id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] is None


# ---------------------------------------------------------------------------
# DELETE /api/v1/work-item-drafts/{id}
# ---------------------------------------------------------------------------


class TestDeleteWorkItemDrafts:
    async def test_owner_can_delete_draft(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        r = await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {}, "local_version": 0},
            cookies={"access_token": token},
        )
        draft_id = r.json()["data"]["draft_id"]

        resp = await http.delete(
            f"/api/v1/work-item-drafts/{draft_id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 204

    async def test_non_owner_gets_403(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)

        # Create draft as user
        r = await http.post(
            "/api/v1/work-item-drafts",
            json={"workspace_id": str(ws.id), "data": {}, "local_version": 0},
            cookies={"access_token": token},
        )
        draft_id = r.json()["data"]["draft_id"]

        # Create second user in same workspace
        engine = create_async_engine(migrated_database.database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            users2 = UserRepositoryImpl(session)
            memberships2 = WorkspaceMembershipRepositoryImpl(session)
            user2 = User.from_google_claims(
                sub=f"sub-{uuid4().hex[:8]}",
                email=f"u2-{uuid4().hex[:6]}@test.com",
                name="U2",
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
        token2 = jwt.encode(
            {
                "sub": str(user2.id),
                "email": user2.email,
                "workspace_id": str(ws.id),
                "is_superadmin": False,
                "exp": int(time.time()) + 3600,
            }
        )

        resp = await http.delete(
            f"/api/v1/work-item-drafts/{draft_id}",
            cookies={"access_token": token2},
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# PATCH /api/v1/work-items/{id}/draft
# ---------------------------------------------------------------------------


class TestPatchWorkItemDraft:
    async def _create_work_item(self, http, token, ws_id):
        r = await http.post(
            "/api/v1/work-items",
            json={
                "title": "Test item",
                "type": "bug",
                "project_id": str(uuid4()),
            },
            cookies={"access_token": token},
        )
        return r.json()["data"]["id"]

    async def test_draft_state_item_returns_200(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        item_id = await self._create_work_item(http, token, ws.id)

        resp = await http.patch(
            f"/api/v1/work-items/{item_id}/draft",
            json={"draft_data": {"description": "partial"}},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == item_id
        assert "draft_saved_at" in body["data"]

    async def test_non_draft_state_returns_409(self, http: AsyncClient, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        item_id = await self._create_work_item(http, token, ws.id)

        # Transition to IN_CLARIFICATION
        await http.post(
            f"/api/v1/work-items/{item_id}/transitions",
            json={"target_state": "in_clarification"},
            cookies={"access_token": token},
        )

        resp = await http.patch(
            f"/api/v1/work-items/{item_id}/draft",
            json={"draft_data": {"description": "too late"}},
            cookies={"access_token": token},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "INVALID_STATE"

    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.patch(
            f"/api/v1/work-items/{uuid4()}/draft",
            json={"draft_data": {}},
        )
        assert resp.status_code == 401
