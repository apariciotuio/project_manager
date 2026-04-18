"""EP-10 — Integration tests for admin members REST API."""

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

_JWT = JwtAdapter(
    secret="change-me-in-prod-use-32-chars-or-more-please",
    issuer="wmp",
    audience="wmp-web",
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
                "TRUNCATE TABLE invitations, context_presets, validation_rules, jira_configs, "
                "routing_rules, validation_rule_templates, projects, "
                "workspace_memberships, sessions, oauth_states, workspaces, users, "
                "rate_limit_buckets "
                "RESTART IDENTITY CASCADE"
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
            sub=f"sub-admin-{uuid4().hex[:6]}",
            email=f"admin-{uuid4().hex[:6]}@test.com",
            name="Admin",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"admin-ws-{uuid4().hex[:6]}"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role=role, is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    token = _JWT.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, ws, token


_CSRF_TOKEN = "test-csrf-token"


def _auth_cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": _CSRF_TOKEN}


def _csrf_headers() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF_TOKEN}


class TestAdminMembersList:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/members",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "data" in body
        assert "items" in body["data"]

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.get(
            "/api/v1/admin/members",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403, resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_gets_401(self, http, migrated_database) -> None:
        resp = await http.get("/api/v1/admin/members")
        assert resp.status_code == 401, resp.text


class TestAdminMembersInvite:
    @pytest.mark.asyncio
    async def test_invite_new_member(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/members",
            json={
                "email": "newmember@example.com",
                "context_labels": [],
                "team_ids": [],
                "initial_capabilities": [],
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert "invitation_id" in body["data"]

    @pytest.mark.asyncio
    async def test_invite_invalid_capability_422(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/members",
            json={"email": "user@example.com", "initial_capabilities": ["fly_to_moon"]},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_invite_pending_returns_409(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        # First invite succeeds
        resp1 = await http.post(
            "/api/v1/admin/members",
            json={"email": "pending@example.com"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp1.status_code == 201, resp1.text

        # Second invite to same email returns 409
        resp2 = await http.post(
            "/api/v1/admin/members",
            json={"email": "pending@example.com"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp2.status_code == 409, resp2.text
        assert resp2.json()["error"]["code"] == "invite_pending"

    @pytest.mark.asyncio
    async def test_non_admin_invite_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.post(
            "/api/v1/admin/members",
            json={"email": "x@example.com"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 403, resp.text


class TestAdminContextPresets:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/context-presets",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_create_and_get(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/context-presets",
            json={"name": "Test Preset", "description": "desc", "sources": []},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 201, resp.text
        created_id = resp.json()["data"]["id"]

        resp2 = await http.get(
            f"/api/v1/admin/context-presets/{created_id}",
            cookies=_auth_cookies(token),
        )
        assert resp2.status_code == 200, resp2.text
        assert resp2.json()["data"]["name"] == "Test Preset"

    @pytest.mark.asyncio
    async def test_create_duplicate_name_409(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        await http.post(
            "/api/v1/admin/context-presets",
            json={"name": "Dupe"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        resp = await http.post(
            "/api/v1/admin/context-presets",
            json={"name": "Dupe"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 409, resp.text

    @pytest.mark.asyncio
    async def test_delete_preset(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/context-presets",
            json={"name": "ToDelete"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        preset_id = resp.json()["data"]["id"]

        del_resp = await http.delete(
            f"/api/v1/admin/context-presets/{preset_id}",
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert del_resp.status_code == 204, del_resp.text


class TestAdminValidationRules:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/rules/validation",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_create_rule(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/rules/validation",
            json={
                "work_item_type": "feature",
                "validation_type": "acceptance_criteria",
                "enforcement": "required",
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["data"]["enforcement"] == "required"

    @pytest.mark.asyncio
    async def test_create_duplicate_409(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        await http.post(
            "/api/v1/admin/rules/validation",
            json={"work_item_type": "feature", "validation_type": "ac", "enforcement": "required"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        resp = await http.post(
            "/api/v1/admin/rules/validation",
            json={
                "work_item_type": "feature",
                "validation_type": "ac",
                "enforcement": "recommended",
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "rule_already_exists"

    @pytest.mark.asyncio
    async def test_delete_rule_no_history(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/rules/validation",
            json={"work_item_type": "bug", "validation_type": "reviewer_approval"},
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        rule_id = resp.json()["data"]["id"]
        del_resp = await http.delete(
            f"/api/v1/admin/rules/validation/{rule_id}",
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert del_resp.status_code == 204, del_resp.text

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.get(
            "/api/v1/admin/rules/validation",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403, resp.text


class TestAdminJiraConfig:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/integrations/jira",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_create_config(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/integrations/jira",
            json={
                "base_url": "https://jira.example.com",
                "auth_type": "basic",
                "credentials": {"token": "secret", "email": "admin@example.com"},
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # credentials must NOT be in response
        assert "credentials" not in str(body)
        assert "secret" not in str(body)
        assert body["data"]["state"] == "active"

    @pytest.mark.asyncio
    async def test_create_http_url_422(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/integrations/jira",
            json={
                "base_url": "http://jira.example.com",
                "auth_type": "basic",
                "credentials": {"token": "t"},
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_get_config_no_credentials(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        create = await http.post(
            "/api/v1/admin/integrations/jira",
            json={
                "base_url": "https://jira2.example.com",
                "auth_type": "basic",
                "credentials": {"token": "topsecret"},
            },
            cookies=_auth_cookies(token),
            headers=_csrf_headers(),
        )
        config_id = create.json()["data"]["id"]

        resp = await http.get(
            f"/api/v1/admin/integrations/jira/{config_id}",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text
        # Confirm credentials_ref never leaks
        assert "topsecret" not in resp.text
        assert "credentials_ref" not in resp.json()["data"]

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.get(
            "/api/v1/admin/integrations/jira",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403, resp.text


class TestAdminDashboard:
    @pytest.mark.asyncio
    async def test_dashboard_returns_health_data(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/dashboard",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        data = body["data"]
        assert "workspace_health" in data
        assert "org_health" in data
        assert "integration_health" in data

    @pytest.mark.asyncio
    async def test_dashboard_non_admin_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.get(
            "/api/v1/admin/dashboard",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403, resp.text


class TestAdminSupport:
    @pytest.mark.asyncio
    async def test_orphaned_work_items_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/support/orphaned-work-items",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_pending_invitations_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/support/pending-invitations",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_failed_exports_empty(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database)
        resp = await http.get(
            "/api/v1/admin/support/failed-exports",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, role="member")
        resp = await http.get(
            "/api/v1/admin/support/orphaned-work-items",
            cookies=_auth_cookies(token),
        )
        assert resp.status_code == 403, resp.text
