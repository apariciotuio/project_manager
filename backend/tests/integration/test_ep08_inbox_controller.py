"""Integration tests — EP-08 inbox REST endpoints (Group C, C3.1).

RED phase: failing tests before controller implementation.

Covers:
  GET /api/v1/inbox          — tiered structure, type filter, user-scoped
  GET /api/v1/inbox/count    — per-tier counts + total

Security:
  - Unauthenticated requests → 401
  - Inbox is user-scoped — user A cannot see user B's items
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


def _make_token(user_id: object, workspace_id: object) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@ep08inbox.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "notifications, "
                "review_responses, review_requests, "
                "timeline_events, comments, work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
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


@pytest_asyncio.fixture
async def seeded(migrated_database):
    """Seed a user + workspace. Returns (user_id, workspace_id, token)."""
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        uid = uuid4().hex[:6]
        user = User.from_google_claims(
            sub=f"inbox-{uid}", email=f"inbox-{uid}@test.com", name="InboxUser", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"inbox-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    return user.id, ws.id, token


# ---------------------------------------------------------------------------
# GET /api/v1/inbox
# ---------------------------------------------------------------------------


class TestGetInbox:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get("/api/v1/inbox")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_inbox_returns_tiers_structure(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.get(
            "/api/v1/inbox", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert "tiers" in data
        assert "total" in data
        assert data["total"] == 0
        for tier_num in ("1", "2", "3", "4"):
            assert tier_num in data["tiers"]
            tier = data["tiers"][tier_num]
            assert tier["count"] == 0
            assert tier["items"] == []

    @pytest.mark.asyncio
    async def test_tier_labels_present(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.get(
            "/api/v1/inbox", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        tiers = resp.json()["data"]["tiers"]
        assert tiers["1"]["label"] == "Pending reviews"
        assert tiers["2"]["label"] == "Returned items"
        assert tiers["3"]["label"] == "Blocking items"
        assert tiers["4"]["label"] == "Decisions needed"


# ---------------------------------------------------------------------------
# GET /api/v1/inbox/count
# ---------------------------------------------------------------------------


class TestGetInboxCount:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get("/api/v1/inbox/count")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_inbox_count(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.get(
            "/api/v1/inbox/count", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert "by_tier" in data
        assert "total" in data
        assert data["total"] == 0
        for tier_num in ("1", "2", "3", "4"):
            assert data["by_tier"][tier_num] == 0
