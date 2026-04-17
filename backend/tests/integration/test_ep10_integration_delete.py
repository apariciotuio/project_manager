"""EP-10 — Integration tests: DELETE /api/v1/integrations/configs/{id}."""
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
                "TRUNCATE TABLE integration_exports, integration_configs, projects, "
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


async def _seed(migrated_database):
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-intdel-{uuid4().hex[:6]}",
            email=f"intdel-{uuid4().hex[:6]}@test.com",
            name="IntDel",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"intdel-{uuid4().hex[:6]}"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
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


class TestDeleteIntegrationConfig:
    @pytest.mark.asyncio
    async def test_delete_success(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        # Create a config
        create_resp = await http.post(
            "/api/v1/integrations/configs",
            json={
                "integration_type": "jira",
                "encrypted_credentials": "enc-creds-test",
            },
            cookies={"access_token": token},
        )
        assert create_resp.status_code == 201, create_resp.text
        config_id = create_resp.json()["data"]["id"]

        # Delete it
        del_resp = await http.delete(
            f"/api/v1/integrations/configs/{config_id}",
            cookies={"access_token": token},
        )
        assert del_resp.status_code == 204

        # Verify gone from list
        list_resp = await http.get(
            "/api/v1/integrations/configs", cookies={"access_token": token}
        )
        assert list_resp.status_code == 200
        ids = [c["id"] for c in list_resp.json()["data"]]
        assert config_id not in ids

    @pytest.mark.asyncio
    async def test_delete_nonexistent_404(self, http, migrated_database) -> None:
        _, _, token = await _seed(migrated_database)
        resp = await http.delete(
            f"/api/v1/integrations/configs/{uuid4()}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cross_workspace_404(self, http, migrated_database) -> None:
        """Cross-workspace access returns 404, not 403 (IDOR mitigation)."""
        _, _, token1 = await _seed(migrated_database)
        _, _, token2 = await _seed(migrated_database)

        create_resp = await http.post(
            "/api/v1/integrations/configs",
            json={"integration_type": "jira", "encrypted_credentials": "enc"},
            cookies={"access_token": token1},
        )
        config_id = create_resp.json()["data"]["id"]

        resp = await http.delete(
            f"/api/v1/integrations/configs/{config_id}",
            cookies={"access_token": token2},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_unauthenticated_401(self, http, migrated_database) -> None:
        resp = await http.delete(f"/api/v1/integrations/configs/{uuid4()}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_requires_workspace(self, http, migrated_database) -> None:
        """GET without workspace in JWT returns 401."""
        jwt = _JWT.encode(
            {
                "sub": str(uuid4()),
                "email": "no-ws@test.com",
                "workspace_id": None,
                "is_superadmin": False,
                "exp": int(time.time()) + 3600,
            }
        )
        resp = await http.get(
            "/api/v1/integrations/configs", cookies={"access_token": jwt}
        )
        assert resp.status_code == 401
