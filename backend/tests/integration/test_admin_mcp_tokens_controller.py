"""EP-18 — Integration tests for admin MCP tokens REST API.

Covers: happy path + auth + authz + cross-workspace isolation per endpoint.
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

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

_PEPPER = "dev-mcp-pepper-change-me-in-prod-32chars"
_CSRF = "test-csrf-token"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE mcp_tokens, rate_limit_buckets, "
                "workspace_memberships, sessions, oauth_states, "
                "workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    import os
    os.environ["MCP_TOKEN_PEPPER"] = _PEPPER

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


async def _seed(
    migrated_database,
    *,
    role: str = "admin",
    capabilities: list[str] | None = None,
) -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-mcp-{uuid4().hex[:6]}",
            email=f"mcp-{uuid4().hex[:6]}@test.com",
            name="MCP Tester",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"mcp-ws-{uuid4().hex[:6]}"
        await workspaces.create(ws)

        membership = WorkspaceMembership.create(
            workspace_id=ws.id,
            user_id=user.id,
            role=role,
            is_default=True,
        )
        await memberships.create(membership)

        # Set capabilities directly on the ORM row (domain model doesn't carry them)
        if capabilities is not None:
            from sqlalchemy import update
            from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

            await session.execute(
                update(WorkspaceMembershipORM)
                .where(
                    WorkspaceMembershipORM.workspace_id == ws.id,
                    WorkspaceMembershipORM.user_id == user.id,
                )
                .values(capabilities=capabilities)
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


def _cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": _CSRF}


def _csrf() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF}


class TestIssueToken:
    @pytest.mark.asyncio
    async def test_issue_happy_path(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "CI Bot", "expires_in_days": 30},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["plaintext"].startswith("mcp_")
        assert "id" in body
        assert "expires_at" in body

    @pytest.mark.asyncio
    async def test_issue_unauthenticated_returns_4xx(self, http, migrated_database) -> None:
        # No auth cookie, no CSRF token — CSRF check fires first (403), then auth (401)
        _, ws, _ = await _seed(migrated_database)
        resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(uuid4()), "name": "Bot"},
        )
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_issue_without_mcp_issue_capability_returns_403(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=[])
        resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "Bot"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_issue_user_not_in_workspace_returns_400(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(uuid4()), "name": "Stranger"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "USER_NOT_IN_WORKSPACE"

    @pytest.mark.asyncio
    async def test_plaintext_only_appears_in_issue_response(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "OnceOnly"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        plaintext = issue_resp.json()["data"]["plaintext"]
        token_id = issue_resp.json()["data"]["id"]

        # List should NOT contain the plaintext
        list_resp = await http.get(
            f"/api/v1/admin/mcp-tokens?user_id={user.id}",
            cookies=_cookies(token),
        )
        list_body = list_resp.json()
        assert plaintext not in str(list_body)


class TestListTokens:
    @pytest.mark.asyncio
    async def test_list_happy_path(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        # Issue one token first
        await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "Listed"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        resp = await http.get(
            f"/api/v1/admin/mcp-tokens?user_id={user.id}",
            cookies=_cookies(token),
        )
        assert resp.status_code == 200
        tokens = resp.json()["data"]
        assert len(tokens) == 1
        assert tokens[0]["name"] == "Listed"
        assert "plaintext" not in tokens[0]
        assert "token_hash_argon2" not in tokens[0]

    @pytest.mark.asyncio
    async def test_admin_cannot_list_tokens_from_other_workspace(
        self, http, migrated_database
    ) -> None:
        user_a, ws_a, token_a = await _seed(migrated_database, capabilities=["mcp:issue"])
        user_b, ws_b, token_b = await _seed(migrated_database, capabilities=["mcp:issue"])

        # Issue a token for user_b in ws_b
        await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user_b.id), "name": "WsB Token"},
            cookies=_cookies(token_b),
            headers=_csrf(),
        )

        # Admin A tries to list tokens for user_b — should return empty (different workspace)
        resp = await http.get(
            f"/api/v1/admin/mcp-tokens?user_id={user_b.id}",
            cookies=_cookies(token_a),
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


class TestRevokeToken:
    @pytest.mark.asyncio
    async def test_revoke_happy_path(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "ToRevoke"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        token_id = issue_resp.json()["data"]["id"]

        resp = await http.delete(
            f"/api/v1/admin/mcp-tokens/{token_id}",
            cookies=_cookies(token),
            headers=_csrf(),
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_revoke_is_idempotent(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "Idempotent"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        token_id = issue_resp.json()["data"]["id"]

        await http.delete(f"/api/v1/admin/mcp-tokens/{token_id}", cookies=_cookies(token), headers=_csrf())
        resp2 = await http.delete(f"/api/v1/admin/mcp-tokens/{token_id}", cookies=_cookies(token), headers=_csrf())
        assert resp2.status_code == 204

    @pytest.mark.asyncio
    async def test_revoke_cross_workspace_returns_404(self, http, migrated_database) -> None:
        user_a, ws_a, token_a = await _seed(migrated_database, capabilities=["mcp:issue"])
        user_b, ws_b, token_b = await _seed(migrated_database, capabilities=["mcp:issue"])

        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user_b.id), "name": "WsB Token"},
            cookies=_cookies(token_b),
            headers=_csrf(),
        )
        token_id = issue_resp.json()["data"]["id"]

        # Admin A tries to revoke token from ws_b — must 404
        resp = await http.delete(
            f"/api/v1/admin/mcp-tokens/{token_id}",
            cookies=_cookies(token_a),
            headers=_csrf(),
        )
        assert resp.status_code == 404


class TestRotateToken:
    @pytest.mark.asyncio
    async def test_rotate_happy_path(self, http, migrated_database) -> None:
        user, ws, token = await _seed(migrated_database, capabilities=["mcp:issue"])
        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user.id), "name": "ToRotate"},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        old_token_id = issue_resp.json()["data"]["id"]
        old_plaintext = issue_resp.json()["data"]["plaintext"]

        resp = await http.post(
            f"/api/v1/admin/mcp-tokens/{old_token_id}/rotate",
            json={},
            cookies=_cookies(token),
            headers=_csrf(),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["id"] != old_token_id
        assert body["plaintext"] != old_plaintext
        assert body["plaintext"].startswith("mcp_")
        assert body["name"] == "ToRotate"

    @pytest.mark.asyncio
    async def test_rotate_cross_workspace_returns_404(self, http, migrated_database) -> None:
        user_a, ws_a, token_a = await _seed(migrated_database, capabilities=["mcp:issue"])
        user_b, ws_b, token_b = await _seed(migrated_database, capabilities=["mcp:issue"])

        issue_resp = await http.post(
            "/api/v1/admin/mcp-tokens",
            json={"user_id": str(user_b.id), "name": "B Token"},
            cookies=_cookies(token_b),
            headers=_csrf(),
        )
        token_b_id = issue_resp.json()["data"]["id"]

        resp = await http.post(
            f"/api/v1/admin/mcp-tokens/{token_b_id}/rotate",
            json={},
            cookies=_cookies(token_a),
            headers=_csrf(),
        )
        assert resp.status_code == 404
