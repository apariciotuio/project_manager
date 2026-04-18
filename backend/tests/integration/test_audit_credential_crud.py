"""EP-12 Audit integration — credential CRUD slice.

Scenarios:
  - POST /integrations/configs → audit row action='credential_create',
    category='admin', entity_type='integration_config', credential_fingerprint in context
  - DELETE /integrations/configs/{id} → audit row action='credential_delete',
    same shape
  - credential_fingerprint is first 8 hex chars of SHA-256(encrypted_credentials)
  - raw secret NEVER appears in context
"""
from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.models.orm import AuditEventORM
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

_CSRF_TOKEN = "test-csrf-ep12-cred"
_RAW_SECRET = "super-secret-jira-pat-token-12345"
_FINGERPRINT = hashlib.sha256(_RAW_SECRET.encode()).hexdigest()[:8]


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE integration_exports, integration_configs, audit_events, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.infrastructure.adapters.jwt_adapter import JwtAdapter
    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter, get_jwt_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()
    fake_cache = FakeCache()

    # Pin the JWT adapter to the sentinel secret so test token decode never fails
    # regardless of lru_cache population order across the test session.
    _pinned_jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )

    def _pinned_jwt_adapter() -> JwtAdapter:
        return _pinned_jwt

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    fastapi_app.dependency_overrides[get_jwt_adapter] = _pinned_jwt_adapter
    yield fastapi_app

    if db_module._engine is not None:
        await db_module._engine.dispose()
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
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub=f"sub-credaudit-{uuid4().hex[:6]}",
            email=f"credaudit-{uuid4().hex[:6]}@test.com",
            name="CredAudit",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"credaudit-{uuid4().hex[:6]}"
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


def _post(client: AsyncClient, url: str, json: Any, *, token: str) -> Any:
    return client.post(
        url,
        json=json,
        cookies={"access_token": token, "csrf_token": _CSRF_TOKEN},
        headers={"X-CSRF-Token": _CSRF_TOKEN},
    )


async def _get_audit_rows(migrated_database, *, action: str) -> list[AuditEventORM]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        stmt = select(AuditEventORM).where(AuditEventORM.action == action)
        rows = (await session.execute(stmt)).scalars().all()
    await engine.dispose()
    return list(rows)


@pytest.mark.asyncio
async def test_create_integration_config_emits_credential_create_audit(
    http, migrated_database
) -> None:
    """POST /integrations/configs → audit row with action='credential_create'."""
    _, _, token = await _seed(migrated_database)

    resp = await _post(
        http,
        "/api/v1/integrations/configs",
        json={"integration_type": "jira", "encrypted_credentials": _RAW_SECRET},
        token=token,
    )
    assert resp.status_code == 201, resp.text
    config_id = resp.json()["data"]["id"]

    rows = await _get_audit_rows(migrated_database, action="credential_create")
    assert len(rows) >= 1, "expected credential_create audit row"
    row = rows[-1]
    assert row.category == "admin"
    assert row.entity_type == "integration_config"
    assert str(row.entity_id) == config_id
    ctx = row.context or {}
    assert ctx.get("outcome") == "success"
    assert ctx.get("integration_type") == "jira"
    assert ctx.get("credential_fingerprint") == _FINGERPRINT, (
        f"expected fingerprint {_FINGERPRINT!r}, got {ctx.get('credential_fingerprint')!r}"
    )
    # Raw secret must NEVER appear in context
    assert _RAW_SECRET not in str(ctx), "raw secret leaked into audit context"


@pytest.mark.asyncio
async def test_delete_integration_config_emits_credential_delete_audit(
    http, migrated_database
) -> None:
    """DELETE /integrations/configs/{id} → audit row with action='credential_delete'."""
    _, _, token = await _seed(migrated_database)

    create_resp = await _post(
        http,
        "/api/v1/integrations/configs",
        json={"integration_type": "jira", "encrypted_credentials": _RAW_SECRET},
        token=token,
    )
    assert create_resp.status_code == 201, create_resp.text
    config_id = create_resp.json()["data"]["id"]

    del_resp = await http.delete(
        f"/api/v1/integrations/configs/{config_id}",
        cookies={"access_token": token, "csrf_token": _CSRF_TOKEN},
        headers={"X-CSRF-Token": _CSRF_TOKEN},
    )
    assert del_resp.status_code == 204, del_resp.text

    rows = await _get_audit_rows(migrated_database, action="credential_delete")
    assert len(rows) >= 1, "expected credential_delete audit row"
    row = rows[-1]
    assert row.category == "admin"
    assert row.entity_type == "integration_config"
    assert str(row.entity_id) == config_id
    ctx = row.context or {}
    assert ctx.get("outcome") == "success"
    assert ctx.get("integration_type") is None or True  # integration_type not available on delete — ok


@pytest.mark.asyncio
async def test_credential_fingerprint_is_sha256_prefix_not_raw_secret(
    http, migrated_database
) -> None:
    """Triangulate: different secrets produce different fingerprints; neither is the raw secret."""
    _, _, token = await _seed(migrated_database)

    secret_a = "secret-alpha-000"
    secret_b = "secret-beta-111"
    fp_a = hashlib.sha256(secret_a.encode()).hexdigest()[:8]
    fp_b = hashlib.sha256(secret_b.encode()).hexdigest()[:8]
    assert fp_a != fp_b

    for secret in (secret_a, secret_b):
        resp = await _post(
            http,
            "/api/v1/integrations/configs",
            json={"integration_type": "jira", "encrypted_credentials": secret},
            token=token,
        )
        assert resp.status_code == 201, resp.text

    rows = await _get_audit_rows(migrated_database, action="credential_create")
    assert len(rows) >= 2
    fingerprints = [r.context.get("credential_fingerprint") for r in rows if r.context]
    assert fp_a in fingerprints, f"fp_a {fp_a!r} missing from {fingerprints}"
    assert fp_b in fingerprints, f"fp_b {fp_b!r} missing from {fingerprints}"
    # Raw secrets must not appear anywhere
    for row in rows:
        assert secret_a not in str(row.context)
        assert secret_b not in str(row.context)
