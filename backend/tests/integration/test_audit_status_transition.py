"""EP-12 Audit — status transition slice.

Scenarios:
  - valid transition → audit row: action='state_transition', category='domain',
    entity_type='work_item', before_value/after_value set, context.outcome='success',
    context.ip_address present.
  - invalid FSM transition → audit row: action='state_transition',
    context.outcome='failure', context.ip_address present.
  - NOT_OWNER transition attempt → audit row with outcome='failure'.
"""

from __future__ import annotations

import time
from uuid import UUID

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
from app.main import create_app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_CSRF_TOKEN = "test-csrf-transition"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    # Dispose any engine left from a previous test before truncating.
    # Timeline event handlers previously leaked "idle in transaction" connections
    # by closing sessions without committing.  That bug is fixed, but we also
    # patch get_engine to use NullPool so the app never pools connections across
    # test boundaries.
    if db_module._engine is not None:
        await db_module._engine.dispose(close=True)
    db_module._engine = None
    db_module._session_factory = None

    _db_url = migrated_database.database.url

    def _nullpool_engine() -> "AsyncEngine":
        if db_module._engine is None:
            db_module._engine = create_async_engine(_db_url, poolclass=NullPool)
        return db_module._engine

    _original_get_engine = db_module.get_engine
    db_module.get_engine = _nullpool_engine  # type: ignore[assignment]

    truncate_engine = create_async_engine(_db_url, poolclass=NullPool)
    async with truncate_engine.begin() as conn:
        # Truncate child tables first (no FK deps), then parents.
        # state_transitions/ownership_history have row-level no-delete triggers
        # but TRUNCATE is statement-level and does NOT fire FOR EACH ROW triggers.
        # audit_events is excluded — append-only with no-delete trigger; queries
        # are scoped by action so accumulation across tests is acceptable.
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "state_transitions, ownership_history, "
                "work_items, workspace_memberships, sessions, oauth_states, "
                "workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await truncate_engine.dispose(close=True)

    from app.infrastructure.adapters.jwt_adapter import JwtAdapter as _JwtAdapter
    from app.presentation.dependencies import get_cache_adapter, get_jwt_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = create_app()

    _pinned_jwt = _JwtAdapter(
        secret=_JWT_SECRET,
        issuer="wmp",
        audience="wmp-web",
    )

    def _pinned_jwt_adapter() -> _JwtAdapter:
        return _pinned_jwt

    async def _override_cache():
        yield FakeCache()

    fastapi_app.dependency_overrides[get_jwt_adapter] = _pinned_jwt_adapter
    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache

    yield fastapi_app

    # Teardown: close all connections before the next test can TRUNCATE.
    if db_module._engine is not None:
        await db_module._engine.dispose(close=True)
    db_module._engine = None
    db_module._session_factory = None
    db_module.get_engine = _original_get_engine  # type: ignore[assignment]


@pytest_asyncio.fixture
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed(migrated_database) -> tuple[User, Workspace]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-trans-audit", email="trans@test.com", name="Trans Tester", picture=None
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="trans@test.com", created_by=user.id)
        ws.slug = "trans-ws"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()
    return user, ws


def _mint_jwt(user: User, ws: Workspace) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


def _cookies(token: str) -> dict[str, str]:
    return {"access_token": token, "csrf_token": _CSRF_TOKEN}


def _headers() -> dict[str, str]:
    return {"X-CSRF-Token": _CSRF_TOKEN}


async def _get_audit_rows(
    migrated_database, *, action: str
) -> list[AuditEventORM]:
    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        stmt = select(AuditEventORM).where(AuditEventORM.action == action)
        rows = (await session.execute(stmt)).scalars().all()
    await engine.dispose()
    return list(rows)


async def _create_work_item(http: AsyncClient, token: str) -> str:
    resp = await http.post(
        "/api/v1/work-items",
        json={"title": "Audit transition item", "type": "story"},
        cookies=_cookies(token),
        headers=_headers(),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_valid_transition_writes_success_audit(http, migrated_database) -> None:
    """Valid FSM transition → audit row with outcome='success', before/after values set,
    ip_address in context."""
    user, ws = await _seed(migrated_database)
    token = _mint_jwt(user, ws)
    item_id = await _create_work_item(http, token)

    resp = await http.post(
        f"/api/v1/work-items/{item_id}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_cookies(token),
        headers=_headers(),
    )
    assert resp.status_code == 200, resp.text

    rows = await _get_audit_rows(migrated_database, action="state_transition")
    assert len(rows) >= 1, "expected state_transition audit row"

    row = rows[-1]
    assert row.category == "domain"
    assert row.entity_type == "work_item"
    assert row.entity_id == UUID(item_id)
    assert row.before_value is not None
    assert row.after_value is not None
    assert row.before_value.get("state") == "draft"
    assert row.after_value.get("state") == "in_clarification"

    ctx = row.context or {}
    assert ctx.get("outcome") == "success", f"expected outcome='success', got: {ctx}"
    assert "ip_address" in ctx, f"expected ip_address in context, got: {ctx}"


async def test_valid_transition_audit_records_actor_and_workspace(
    http, migrated_database
) -> None:
    """Success audit row carries actor_id and workspace_id."""
    user, ws = await _seed(migrated_database)
    token = _mint_jwt(user, ws)
    item_id = await _create_work_item(http, token)

    await http.post(
        f"/api/v1/work-items/{item_id}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_cookies(token),
        headers=_headers(),
    )

    rows = await _get_audit_rows(migrated_database, action="state_transition")
    assert rows
    row = rows[-1]
    assert row.actor_id == user.id
    assert row.workspace_id == ws.id


async def test_invalid_fsm_transition_writes_failure_audit(http, migrated_database) -> None:
    """Invalid FSM edge (e.g. draft → exported) → audit row with outcome='failure',
    ip_address in context. HTTP response is 422."""
    user, ws = await _seed(migrated_database)
    token = _mint_jwt(user, ws)
    item_id = await _create_work_item(http, token)

    # draft → exported is a valid WorkItemState enum value but not a valid FSM edge.
    # Using an invalid enum value (e.g. "approved") would be rejected at schema
    # validation before reaching the service, so no audit row would be written.
    resp = await http.post(
        f"/api/v1/work-items/{item_id}/transitions",
        json={"target_state": "exported"},
        cookies=_cookies(token),
        headers=_headers(),
    )
    assert resp.status_code == 422, resp.text

    rows = await _get_audit_rows(migrated_database, action="state_transition")
    assert len(rows) >= 1, "expected failure state_transition audit row"

    row = rows[-1]
    assert row.category == "domain"
    assert row.entity_type == "work_item"
    assert row.entity_id == UUID(item_id)

    ctx = row.context or {}
    assert ctx.get("outcome") == "failure", f"expected outcome='failure', got: {ctx}"
    assert "ip_address" in ctx, f"expected ip_address in context, got: {ctx}"
    assert "error_code" in ctx, f"expected error_code in context, got: {ctx}"
