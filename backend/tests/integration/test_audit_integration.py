"""EP-12 Audit integration — verify audit records are written at required touchpoints.

Scenarios:
  - login success → audit record with action='login_success', outcome='success', ip present in context
  - login failure (no workspace) → audit record with action='login_blocked_no_workspace', outcome='failure'
  - token refresh success → audit record with action='token_refresh'
  - status transition → audit record with action='state_transition', entity_type='work_item',
    before_value/after_value set
  - 403 response → audit record with action='authorization_denied', outcome='failure'
"""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse
from uuid import UUID

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        # audit_events has a BEFORE DELETE trigger — skip it here.
        # Each test function scopes its audit queries by action name so row
        # accumulation across tests is acceptable (tests don't assert on exact count).
        # Tables with no_delete triggers: exclude from TRUNCATE to avoid hangs.
        # CASCADE on work_items will handle state_transitions/ownership_history rows.
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
            sub="sub-audit-test",
            email="audit@test.com",
            name="Audit Tester",
            picture=None,
        )
    )
    fastapi_app.dependency_overrides[get_google_oauth_adapter] = lambda: fake_google
    fastapi_app.state.fake_google = fake_google
    yield fastapi_app

    # Dispose the global engine before resetting to free asyncpg connections
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


async def _seed_user_workspace(migrated_database) -> tuple[User, Workspace]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-audit-test", email="audit@test.com", name="Audit Tester", picture=None
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="audit@test.com", created_by=user.id)
        ws.slug = "audit-ws"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()
    return user, ws


async def _seed_user_no_workspace(migrated_database) -> None:
    """Seed user only — no workspace membership (triggers login failure path)."""
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        user = User.from_google_claims(
            sub="sub-audit-test", email="audit@test.com", name="Audit Tester", picture=None
        )
        await users.upsert(user)
        await session.commit()
    await engine.dispose()


_CSRF_TOKEN = "test-csrf-token-audit"


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


def _auth_cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": _CSRF_TOKEN}


def _auth_headers() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF_TOKEN}


async def _get_audit_rows(migrated_database, *, action: str | None = None) -> list[AuditEventORM]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        stmt = select(AuditEventORM)
        if action:
            stmt = stmt.where(AuditEventORM.action == action)
        rows = (await session.execute(stmt)).scalars().all()
    await engine.dispose()
    return list(rows)


async def _do_oauth_flow(http: AsyncClient) -> None:
    """Drive the Google OAuth flow (initiate → callback)."""
    init = await http.get("/api/v1/auth/google")
    assert init.status_code == 302
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")


# ---------------------------------------------------------------------------
# Login success → audit record
# ---------------------------------------------------------------------------


async def test_login_success_writes_audit_record(http, migrated_database) -> None:
    """Login success writes an audit record with action='login_success', outcome='success'."""
    await _seed_user_workspace(migrated_database)
    await _do_oauth_flow(http)

    rows = await _get_audit_rows(migrated_database, action="login_success")
    assert len(rows) >= 1, "expected at least one login_success audit record"

    row = rows[-1]
    assert row.category == "auth"
    assert row.action == "login_success"
    ctx = row.context or {}
    assert ctx.get("outcome") == "success", f"expected outcome='success' in context, got: {ctx}"
    # ip_address is present (may be None in test, but key must exist)
    assert "ip_address" in ctx, f"expected ip_address key in context, got: {ctx}"


async def test_login_success_audit_records_actor(http, migrated_database) -> None:
    """Login success audit record carries actor_id and actor_display."""
    user, _ = await _seed_user_workspace(migrated_database)
    await _do_oauth_flow(http)

    rows = await _get_audit_rows(migrated_database, action="login_success")
    assert rows, "expected login_success audit record"
    row = rows[-1]
    assert row.actor_id == user.id
    assert row.actor_display == user.email


# ---------------------------------------------------------------------------
# Login failure → audit record
# ---------------------------------------------------------------------------


async def test_login_failure_no_workspace_writes_audit_record(http, migrated_database) -> None:
    """Login failure (no workspace) writes an audit record with outcome='failure'."""
    await _seed_user_no_workspace(migrated_database)

    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    resp = await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")
    assert resp.status_code == 302
    assert "no_workspace" in resp.headers["location"]

    rows = await _get_audit_rows(migrated_database, action="login_blocked_no_workspace")
    assert len(rows) >= 1, "expected login failure audit record"

    row = rows[-1]
    assert row.category == "auth"
    ctx = row.context or {}
    assert ctx.get("outcome") == "failure", f"expected outcome='failure' in context, got: {ctx}"
    assert "ip_address" in ctx, f"expected ip_address in context, got: {ctx}"


# ---------------------------------------------------------------------------
# Token refresh → audit record
# ---------------------------------------------------------------------------


async def test_token_refresh_writes_audit_record(http, migrated_database) -> None:
    """Successful token refresh writes an audit record with action='token_refresh'."""
    await _seed_user_workspace(migrated_database)

    # Full login to get cookies
    init = await http.get("/api/v1/auth/google")
    state = parse_qs(urlparse(init.headers["location"]).query)["state"][0]
    callback_resp = await http.get(f"/api/v1/auth/google/callback?code=dummy-code&state={state}")
    assert callback_resp.status_code == 302

    # Hit refresh endpoint (cookies are carried by the client)
    refresh_resp = await http.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200

    rows = await _get_audit_rows(migrated_database, action="token_refresh")
    assert len(rows) >= 1, "expected token_refresh audit record"

    row = rows[-1]
    assert row.category == "auth"
    assert row.action == "token_refresh"


# ---------------------------------------------------------------------------
# Status transition → audit record
# ---------------------------------------------------------------------------


async def test_state_transition_writes_audit_record(http, migrated_database) -> None:
    """Work item status transition writes audit with action='state_transition',
    entity_type='work_item', before_value/after_value set."""
    user, ws = await _seed_user_workspace(migrated_database)
    token = _mint_jwt(user, ws)

    # Create a work item
    create_resp = await http.post(
        "/api/v1/work-items",
        json={"title": "Audit transition test", "type": "story"},
        cookies=_auth_cookies(token),
        headers=_auth_headers(),
    )
    assert create_resp.status_code == 201, create_resp.text
    item_id = create_resp.json()["data"]["id"]

    # Transition: draft → in_progress
    trans_resp = await http.post(
        f"/api/v1/work-items/{item_id}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_auth_cookies(token),
        headers=_auth_headers(),
    )
    assert trans_resp.status_code == 200, trans_resp.text

    rows = await _get_audit_rows(migrated_database, action="state_transition")
    assert len(rows) >= 1, "expected state_transition audit record"

    row = rows[-1]
    # category='domain' is used (DB check constraint only allows auth/admin/domain)
    assert row.category == "domain"
    assert row.entity_type == "work_item"
    assert row.entity_id == UUID(item_id)
    assert row.before_value is not None
    assert row.after_value is not None
    assert row.before_value.get("state") == "draft"
    assert row.after_value.get("state") == "in_clarification"


async def test_state_transition_audit_records_actor_and_workspace(http, migrated_database) -> None:
    """Status transition audit carries actor_id and workspace_id."""
    user, ws = await _seed_user_workspace(migrated_database)
    token = _mint_jwt(user, ws)

    create_resp = await http.post(
        "/api/v1/work-items",
        json={"title": "Actor workspace test", "type": "story"},
        cookies=_auth_cookies(token),
        headers=_auth_headers(),
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["data"]["id"]

    await http.post(
        f"/api/v1/work-items/{item_id}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_auth_cookies(token),
        headers=_auth_headers(),
    )

    rows = await _get_audit_rows(migrated_database, action="state_transition")
    assert rows
    row = rows[-1]
    assert row.actor_id == user.id
    assert row.workspace_id == ws.id


# ---------------------------------------------------------------------------
# 403 response → audit record
# ---------------------------------------------------------------------------


async def _seed_member_user(migrated_database) -> tuple[User, Workspace]:
    """Seed a user with 'member' role (not admin) — triggers 403 on admin-only endpoints."""
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-member-test", email="member@test.com", name="Member", picture=None
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="member@test.com", created_by=user.id)
        ws.slug = "member-ws"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()
    return user, ws


async def test_403_response_writes_authorization_denied_audit(http, migrated_database) -> None:
    """An HTTP 403 response writes an audit record with action='authorization_denied',
    outcome='failure' in context."""
    user, ws = await _seed_member_user(migrated_database)
    token = _mint_jwt(user, ws)

    # Routing rules endpoint requires admin role — member gets 403
    resp = await http.get(
        "/api/v1/routing-rules",
        cookies={"access_token": token},
    )
    assert resp.status_code == 403, f"expected 403, got {resp.status_code}: {resp.text}"

    rows = await _get_audit_rows(migrated_database, action="authorization_denied")
    assert len(rows) >= 1, "expected authorization_denied audit record after 403"

    row = rows[-1]
    assert row.category == "auth"
    ctx = row.context or {}
    assert ctx.get("outcome") == "failure"
