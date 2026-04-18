"""Integration tests — audit log list cursor pagination.

Endpoint: GET /api/v1/admin/audit-events

Scenarios:
  - First page returns envelope {data: {items, pagination: {cursor, has_next}}}
  - Supplying cursor returns next page with no duplicate IDs
  - page_size > 100 → 422
  - Workspace isolation: user A cannot see workspace B events
  - Admin-only: non-admin member → 403
"""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------


def _make_token(user_id: object, workspace_id: object, *, is_superadmin: bool = False) -> str:
    from app.config.settings import get_settings

    settings = get_settings()
    jwt_adapter = JwtAdapter(
        secret=settings.auth.jwt_secret,
        issuer=settings.auth.jwt_issuer,
        audience=settings.auth.jwt_audience,
    )
    return jwt_adapter.encode(
        {
            "sub": str(user_id),
            "email": "test@audit-pagination.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": is_superadmin,
            "exp": int(time.time()) + 3600,
        }
    )


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    async with engine.begin() as conn:
        for tbl in ("state_transitions", "ownership_history"):
            await conn.execute(text(f"ALTER TABLE {tbl} DISABLE TRIGGER ALL"))
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "notifications, timeline_events, comments, "
                "work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
        for tbl in ("state_transitions", "ownership_history"):
            await conn.execute(text(f"ALTER TABLE {tbl} ENABLE TRIGGER ALL"))
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def _seed_workspace(
    migrated_database,
    *,
    slug: str,
    user_role: str = "admin",
) -> tuple[UUID, UUID, str]:
    """Returns (user_id, workspace_id, token)."""
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    uid = uuid4().hex[:8]
    async with factory() as session:
        user = User.from_google_claims(
            sub=f"audit-p-{uid}",
            email=f"audit-p-{uid}@test.com",
            name=f"User-{uid}",
            picture=None,
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = slug
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id,
                user_id=user.id,
                role=user_role,
                is_default=True,
            )
        )
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    return user.id, ws.id, token


async def _insert_audit_events(
    migrated_database,
    workspace_id: UUID,
    *,
    count: int,
    category: str = "domain",
    action: str = "test.action",
) -> list[str]:
    """Insert `count` audit events and return their IDs."""
    from app.domain.models.audit_event import AuditEvent
    from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids: list[str] = []
    async with factory() as session:
        repo = AuditRepositoryImpl(session)
        for _ in range(count):
            event = AuditEvent(
                id=uuid4(),
                category=category,  # type: ignore[arg-type]
                action=action,
                workspace_id=workspace_id,
                actor_display="test-actor",
                context={},
            )
            saved = await repo.append(event)
            ids.append(str(saved.id))
        await session.commit()
    await engine.dispose()
    return ids


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_page_returns_cursor_envelope(http, migrated_database):
    """First page response contains {items, pagination: {cursor, has_next}}."""
    _, ws_id, token = await _seed_workspace(migrated_database, slug="audit-p-1")
    await _insert_audit_events(migrated_database, ws_id, count=5)

    resp = await http.get(
        "/api/v1/admin/audit-events?page_size=3",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "items" in data
    pagination = data["pagination"]
    assert "cursor" in pagination
    assert "has_next" in pagination
    assert pagination["has_next"] is True
    assert pagination["cursor"] is not None
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_cursor_returns_next_page_no_duplicates(http, migrated_database):
    """Supplying the cursor from page 1 returns page 2 with no overlapping IDs."""
    _, ws_id, token = await _seed_workspace(migrated_database, slug="audit-p-2")
    await _insert_audit_events(migrated_database, ws_id, count=7)

    # Page 1
    resp1 = await http.get(
        "/api/v1/admin/audit-events?page_size=4",
        cookies={"access_token": token},
    )
    assert resp1.status_code == 200
    data1 = resp1.json()["data"]
    ids1 = {item["id"] for item in data1["items"]}
    cursor = data1["pagination"]["cursor"]
    assert data1["pagination"]["has_next"] is True

    # Page 2
    resp2 = await http.get(
        f"/api/v1/admin/audit-events?page_size=4&cursor={cursor}",
        cookies={"access_token": token},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()["data"]
    ids2 = {item["id"] for item in data2["items"]}

    assert ids1.isdisjoint(ids2), f"Duplicate IDs across pages: {ids1 & ids2}"
    assert len(data2["items"]) == 3  # 7 - 4 = 3
    assert data2["pagination"]["has_next"] is False


@pytest.mark.asyncio
async def test_page_size_101_returns_422(http, migrated_database):
    """page_size > 100 must return 422."""
    _, ws_id, token = await _seed_workspace(migrated_database, slug="audit-p-3")

    resp = await http.get(
        "/api/v1/admin/audit-events?page_size=101",
        cookies={"access_token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_workspace_isolation(http, migrated_database):
    """User from workspace A cannot see workspace B audit events."""
    _, ws_a, token_a = await _seed_workspace(migrated_database, slug="audit-p-4a")
    _, ws_b, _ = await _seed_workspace(migrated_database, slug="audit-p-4b")

    # Insert events only in workspace B
    await _insert_audit_events(migrated_database, ws_b, count=5)

    resp = await http.get(
        "/api/v1/admin/audit-events",
        cookies={"access_token": token_a},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 0


@pytest.mark.asyncio
async def test_non_admin_returns_403(http, migrated_database):
    """Members without admin role get 403."""
    uid = uuid4().hex[:8]

    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User.from_google_claims(
            sub=f"audit-member-{uid}",
            email=f"audit-member-{uid}@test.com",
            name="Member",
            picture=None,
        )
        await UserRepositoryImpl(session).upsert(user)
        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"audit-p-5-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    resp = await http.get(
        "/api/v1/admin/audit-events",
        cookies={"access_token": token},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_last_page_has_next_false_cursor_none(http, migrated_database):
    """When there are no more pages, has_next=False and cursor=None."""
    _, ws_id, token = await _seed_workspace(migrated_database, slug="audit-p-6")
    await _insert_audit_events(migrated_database, ws_id, count=3)

    resp = await http.get(
        "/api/v1/admin/audit-events?page_size=10",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    pagination = resp.json()["data"]["pagination"]
    assert pagination["has_next"] is False
    assert pagination["cursor"] is None
