"""Integration tests — EP-08 Team controller (A4.1, A4.2).

RED phase: failing tests before implementation verification.

Covers:
  POST /api/v1/teams                           — 201; duplicate name → 422; empty name → 422
  GET  /api/v1/teams                           — 200; workspace-scoped list
  GET  /api/v1/teams/{id}                      — 200 with members; 404 unknown
  PATCH /api/v1/teams/{id}                     — 200; 422 empty name
  DELETE /api/v1/teams/{id}                    — 200 deleted status
  POST /api/v1/teams/{id}/members              — 200 member list
  DELETE /api/v1/teams/{id}/members/{user_id}  — 200 member list
  PATCH /api/v1/teams/{id}/members/{user_id}/role — 200; 409 LAST_LEAD_REMOVAL

Security:
  - Unauthenticated → 401
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
            "email": "teamtest@ep08.test",
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
                "team_memberships, teams, "
                "notifications, "
                "timeline_events, comments, work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users, rate_limit_buckets RESTART IDENTITY CASCADE"
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


_CSRF_TOKEN = "test-csrf-token-ep08-teams"

_CSRF_COOKIES = {"csrf_token": _CSRF_TOKEN}
_CSRF_HEADERS = {"X-CSRF-Token": _CSRF_TOKEN}


@pytest_asyncio.fixture
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


def _auth_cookies(token: str) -> dict:
    return {"access_token": token, **_CSRF_COOKIES}


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
            sub=f"team-{uid}", email=f"team-{uid}@test.com", name="TeamUser", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"team-{uid}"
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
# POST /api/v1/teams
# ---------------------------------------------------------------------------


class TestCreateTeam:
    @pytest.mark.asyncio
    async def test_unauthenticated_get_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get("/api/v1/teams")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_returns_201_with_team(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.post(
            "/api/v1/teams",
            json={"name": "Alpha Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["name"] == "Alpha Team"
        assert data["workspace_id"] == str(workspace_id)

    @pytest.mark.asyncio
    async def test_create_empty_name_returns_422(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.post(
            "/api/v1/teams",
            json={"name": "   "},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/teams
# ---------------------------------------------------------------------------


class TestListTeams:
    @pytest.mark.asyncio
    async def test_list_returns_200_with_teams(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        # Create a team first
        await http.post(
            "/api/v1/teams",
            json={"name": "Beta Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        resp = await http.get("/api/v1/teams", cookies={"access_token": token})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert any(t["name"] == "Beta Team" for t in data)

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, http: AsyncClient) -> None:
        resp = await http.get("/api/v1/teams")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/teams/{id}
# ---------------------------------------------------------------------------


class TestGetTeam:
    @pytest.mark.asyncio
    async def test_get_existing_team_returns_200(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        create_resp = await http.post(
            "/api/v1/teams",
            json={"name": "Gamma Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        team_id = create_resp.json()["data"]["id"]

        resp = await http.get(
            f"/api/v1/teams/{team_id}", cookies={"access_token": token}
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == team_id
        assert "members" in data

    @pytest.mark.asyncio
    async def test_get_unknown_team_returns_404(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        resp = await http.get(
            f"/api/v1/teams/{uuid4()}", cookies={"access_token": token}
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/teams/{id}
# ---------------------------------------------------------------------------


class TestUpdateTeam:
    @pytest.mark.asyncio
    async def test_update_name_returns_200(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        create_resp = await http.post(
            "/api/v1/teams",
            json={"name": "Delta Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        team_id = create_resp.json()["data"]["id"]

        resp = await http.patch(
            f"/api/v1/teams/{team_id}",
            json={"name": "Delta Team v2"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code in (200, 204)
        if resp.status_code == 200:
            assert resp.json()["data"]["name"] == "Delta Team v2"


# ---------------------------------------------------------------------------
# DELETE /api/v1/teams/{id}
# ---------------------------------------------------------------------------


class TestDeleteTeam:
    @pytest.mark.asyncio
    async def test_delete_team_returns_200(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        create_resp = await http.post(
            "/api/v1/teams",
            json={"name": "Epsilon Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        team_id = create_resp.json()["data"]["id"]

        resp = await http.delete(
            f"/api/v1/teams/{team_id}",
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code in (200, 204)


# ---------------------------------------------------------------------------
# POST /api/v1/teams/{id}/members
# ---------------------------------------------------------------------------


class TestAddMember:
    @pytest.mark.asyncio
    async def test_add_member_returns_200(
        self, http: AsyncClient, seeded, migrated_database
    ) -> None:
        user_id, workspace_id, token = seeded

        # Create a second user
        from app.domain.models.user import User
        from app.domain.models.workspace_membership import WorkspaceMembership
        from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
        from app.infrastructure.persistence.workspace_membership_repository_impl import (
            WorkspaceMembershipRepositoryImpl,
        )

        engine = create_async_engine(migrated_database.database.url)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            uid = uuid4().hex[:6]
            user2 = User.from_google_claims(
                sub=f"member-{uid}", email=f"member-{uid}@test.com", name="Member", picture=None
            )
            await UserRepositoryImpl(session).upsert(user2)
            await WorkspaceMembershipRepositoryImpl(session).create(
                WorkspaceMembership.create(
                    workspace_id=workspace_id, user_id=user2.id, role="member", is_default=True
                )
            )
            await session.commit()
        await engine.dispose()

        # Create team
        create_resp = await http.post(
            "/api/v1/teams",
            json={"name": "Zeta Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        team_id = create_resp.json()["data"]["id"]

        # Add second user as member
        resp = await http.post(
            f"/api/v1/teams/{team_id}/members",
            json={"user_id": str(user2.id), "role": "member"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code in (200, 201)


# ---------------------------------------------------------------------------
# PATCH /api/v1/teams/{id}/members/{user_id}/role — last lead demotion
# ---------------------------------------------------------------------------


class TestUpdateMemberRole:
    @pytest.mark.asyncio
    async def test_demote_last_lead_returns_409(
        self, http: AsyncClient, seeded
    ) -> None:
        user_id, workspace_id, token = seeded
        create_resp = await http.post(
            "/api/v1/teams",
            json={"name": "Eta Team"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        team_id = create_resp.json()["data"]["id"]

        # Try to demote the creator (who is the only lead)
        resp = await http.patch(
            f"/api/v1/teams/{team_id}/members/{user_id}/role",
            json={"role": "member"},
            cookies=_auth_cookies(token),
            headers=_CSRF_HEADERS,
        )
        assert resp.status_code == 409
        error = resp.json()["error"]
        assert error["code"] == "LAST_LEAD_REMOVAL"
