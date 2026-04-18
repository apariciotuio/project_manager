"""EP-12 Audit integration — narrow auth slice.

Scenarios:
  - login success (action='login_success') → ip_address in context (already covered in
    test_audit_integration.py; included here for the explicit field assertions)
  - login failure (invalid state) → audit record with action='login_invalid_state', outcome='failure'
  - 403 response → audit record with action='authorization_denied', outcome='failure',
    ip_address present in context
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.google_oauth_adapter import GoogleClaims
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from app.infrastructure.persistence.models.orm import AuditEventORM
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl
from app.main import create_app
from app.presentation.dependencies import get_google_oauth_adapter
from tests.fakes.fake_google_oauth import FakeGoogleOAuthAdapter

import time

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "work_items, workspace_memberships, sessions, oauth_states, "
                "workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    fastapi_app = create_app()
    fake_google = FakeGoogleOAuthAdapter(
        claims=GoogleClaims(
            sub="sub-auth-audit-test",
            email="auth-audit@test.com",
            name="Auth Audit Tester",
            picture=None,
        )
    )
    fastapi_app.dependency_overrides[get_google_oauth_adapter] = lambda: fake_google
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


async def _seed_user_with_workspace(migrated_database) -> tuple[User, Workspace]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-auth-audit-test",
            email="auth-audit@test.com",
            name="Auth Audit Tester",
            picture=None,
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="auth-audit@test.com", created_by=user.id)
        ws.slug = "auth-audit-ws"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()
    return user, ws


async def _get_audit_rows(
    migrated_database, *, action: str | None = None
) -> list[AuditEventORM]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        stmt = select(AuditEventORM)
        if action:
            stmt = stmt.where(AuditEventORM.action == action)
        rows = (await session.execute(stmt)).scalars().all()
    await engine.dispose()
    return list(rows)


def _mint_jwt(user: User, workspace: Workspace) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(workspace.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


# ---------------------------------------------------------------------------
# Login success → ip_address in context
# ---------------------------------------------------------------------------


async def test_login_success_audit_has_ip_address(http, migrated_database) -> None:
    """Login success audit record carries ip_address key in context (may be None in test)."""
    await _seed_user_with_workspace(migrated_database)

    init = await http.get("/api/v1/auth/google")
    assert init.status_code == 302
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")

    rows = await _get_audit_rows(migrated_database, action="login_success")
    assert rows, "expected login_success audit row"
    row = rows[-1]
    assert row.category == "auth"
    ctx = row.context or {}
    assert ctx.get("outcome") == "success"
    assert "ip_address" in ctx, f"ip_address missing from context: {ctx}"
    assert "user_agent" in ctx, f"user_agent missing from context: {ctx}"
    assert row.entity_type == "user", f"expected entity_type='user', got: {row.entity_type}"


# ---------------------------------------------------------------------------
# Login failure — invalid state → audit record
# ---------------------------------------------------------------------------


async def test_login_invalid_state_writes_audit_record(http, migrated_database) -> None:
    """Invalid OAuth state in callback writes audit record with outcome='failure'."""
    resp = await http.get(
        "/api/v1/auth/google/callback?code=dummy-code&state=totally-bogus-state"
    )
    # Controller redirects on invalid state — that's expected
    assert resp.status_code == 302
    assert "invalid_state" in resp.headers["location"]

    rows = await _get_audit_rows(migrated_database, action="login_invalid_state")
    assert len(rows) >= 1, "expected login_invalid_state audit record"
    row = rows[-1]
    assert row.category == "auth"
    ctx = row.context or {}
    assert ctx.get("outcome") == "failure", f"expected outcome=failure, got: {ctx}"
    assert "ip_address" in ctx


# ---------------------------------------------------------------------------
# 403 response → authorization_denied audit with ip_address
# ---------------------------------------------------------------------------


async def test_403_audit_includes_ip_address(http, migrated_database) -> None:
    """403 handler writes authorization_denied audit with ip_address in context."""
    user, ws = await _seed_user_with_workspace(migrated_database)
    token = _mint_jwt(user, ws)

    # routing-rules is admin-only; member role gets 403
    resp = await http.get(
        "/api/v1/routing-rules",
        cookies={"access_token": token},
    )
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"

    rows = await _get_audit_rows(migrated_database, action="authorization_denied")
    assert rows, "expected authorization_denied audit row"
    row = rows[-1]
    assert row.category == "auth"
    ctx = row.context or {}
    assert ctx.get("outcome") == "failure"
    assert "ip_address" in ctx, f"ip_address missing from 403 audit context: {ctx}"
