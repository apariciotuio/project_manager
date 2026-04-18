"""EP-10 — Integration tests for routing rules + validation rule templates REST API."""

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
                "TRUNCATE TABLE routing_rules, validation_rule_templates, projects, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
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
            sub=f"sub-ep10-{uuid4().hex[:6]}",
            email=f"ep10-{uuid4().hex[:6]}@test.com",
            name="EP10",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"ep10-{uuid4().hex[:6]}"
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


# ---------------------------------------------------------------------------
# Routing Rule tests
# ---------------------------------------------------------------------------


class TestRoutingRulesCRUD:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        resp = await http.get("/api/v1/routing-rules", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_create_and_list(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        body = {"work_item_type": "task", "priority": 5}
        resp = await http.post("/api/v1/routing-rules", json=body, cookies={"access_token": token})
        assert resp.status_code == 201, resp.text
        rule_id = resp.json()["data"]["id"]
        assert resp.json()["data"]["work_item_type"] == "task"
        assert resp.json()["data"]["priority"] == 5
        assert resp.json()["data"]["active"] is True

        list_resp = await http.get("/api/v1/routing-rules", cookies={"access_token": token})
        assert len(list_resp.json()["data"]) == 1
        assert list_resp.json()["data"][0]["id"] == rule_id

    @pytest.mark.asyncio
    async def test_get_by_id(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/routing-rules",
            json={"work_item_type": "bug"},
            cookies={"access_token": token},
        )
        rule_id = create_resp.json()["data"]["id"]
        resp = await http.get(f"/api/v1/routing-rules/{rule_id}", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == rule_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_404(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        resp = await http.get(f"/api/v1/routing-rules/{uuid4()}", cookies={"access_token": token})
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_deactivate(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/routing-rules",
            json={"work_item_type": "task"},
            cookies={"access_token": token},
        )
        rule_id = create_resp.json()["data"]["id"]
        patch_resp = await http.patch(
            f"/api/v1/routing-rules/{rule_id}",
            json={"active": False},
            cookies={"access_token": token},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["active"] is False

    @pytest.mark.asyncio
    async def test_patch_priority(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/routing-rules",
            json={"work_item_type": "task", "priority": 0},
            cookies={"access_token": token},
        )
        rule_id = create_resp.json()["data"]["id"]
        patch_resp = await http.patch(
            f"/api/v1/routing-rules/{rule_id}",
            json={"priority": 99},
            cookies={"access_token": token},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["priority"] == 99

    @pytest.mark.asyncio
    async def test_delete(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/routing-rules",
            json={"work_item_type": "task"},
            cookies={"access_token": token},
        )
        rule_id = create_resp.json()["data"]["id"]
        del_resp = await http.delete(
            f"/api/v1/routing-rules/{rule_id}", cookies={"access_token": token}
        )
        assert del_resp.status_code == 204

        get_resp = await http.get(
            f"/api/v1/routing-rules/{rule_id}", cookies={"access_token": token}
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database, role="member")
        resp = await http.post(
            "/api/v1/routing-rules",
            json={"work_item_type": "task"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_gets_401(self, http, migrated_database) -> None:
        resp = await http.get("/api/v1/routing-rules")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Validation Rule Template tests
# ---------------------------------------------------------------------------


class TestValidationRuleTemplatesCRUD:
    @pytest.mark.asyncio
    async def test_list_empty(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        resp = await http.get("/api/v1/validation-rule-templates", cookies={"access_token": token})
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    @pytest.mark.asyncio
    async def test_create_and_list(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        body = {
            "name": "My Template",
            "requirement_type": "reviewer_approval",
            "is_mandatory": True,
            "work_item_type": "task",
        }
        resp = await http.post(
            "/api/v1/validation-rule-templates",
            json=body,
            cookies={"access_token": token},
        )
        assert resp.status_code == 201, resp.text
        tmpl_id = resp.json()["data"]["id"]
        assert resp.json()["data"]["name"] == "My Template"
        assert resp.json()["data"]["is_mandatory"] is True

        list_resp = await http.get(
            "/api/v1/validation-rule-templates", cookies={"access_token": token}
        )
        assert len(list_resp.json()["data"]) == 1
        assert list_resp.json()["data"][0]["id"] == tmpl_id

    @pytest.mark.asyncio
    async def test_create_invalid_type_422(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        body = {
            "name": "Bad",
            "requirement_type": "not_valid_type",
            "is_mandatory": False,
        }
        resp = await http.post(
            "/api/v1/validation-rule-templates",
            json=body,
            cookies={"access_token": token},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_get_by_id(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/validation-rule-templates",
            json={"name": "T", "requirement_type": "custom", "is_mandatory": False},
            cookies={"access_token": token},
        )
        tmpl_id = create_resp.json()["data"]["id"]
        resp = await http.get(
            f"/api/v1/validation-rule-templates/{tmpl_id}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == tmpl_id

    @pytest.mark.asyncio
    async def test_patch_deactivate(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/validation-rule-templates",
            json={"name": "T", "requirement_type": "custom", "is_mandatory": True},
            cookies={"access_token": token},
        )
        tmpl_id = create_resp.json()["data"]["id"]
        patch_resp = await http.patch(
            f"/api/v1/validation-rule-templates/{tmpl_id}",
            json={"active": False},
            cookies={"access_token": token},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["data"]["active"] is False

    @pytest.mark.asyncio
    async def test_delete(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        create_resp = await http.post(
            "/api/v1/validation-rule-templates",
            json={"name": "T", "requirement_type": "custom", "is_mandatory": False},
            cookies={"access_token": token},
        )
        tmpl_id = create_resp.json()["data"]["id"]
        del_resp = await http.delete(
            f"/api/v1/validation-rule-templates/{tmpl_id}",
            cookies={"access_token": token},
        )
        assert del_resp.status_code == 204

        get_resp = await http.get(
            f"/api/v1/validation-rule-templates/{tmpl_id}",
            cookies={"access_token": token},
        )
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_non_admin_gets_403(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database, role="member")
        resp = await http.get("/api/v1/validation-rule-templates", cookies={"access_token": token})
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_404_on_other_workspace(self, http, migrated_database) -> None:
        _, _, token1 = await _seed(migrated_database)
        _, _, token2 = await _seed(migrated_database)

        create_resp = await http.post(
            "/api/v1/validation-rule-templates",
            json={"name": "T", "requirement_type": "custom", "is_mandatory": False},
            cookies={"access_token": token1},
        )
        tmpl_id = create_resp.json()["data"]["id"]

        resp = await http.get(
            f"/api/v1/validation-rule-templates/{tmpl_id}",
            cookies={"access_token": token2},
        )
        assert resp.status_code == 404
