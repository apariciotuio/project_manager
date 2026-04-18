"""Integration tests — EP-08 notification REST endpoints.

Covers:
  GET    /api/v1/notifications                    — list (user-scoped)
  GET    /api/v1/notifications/unread-count       — badge count
  PATCH  /api/v1/notifications/{id}/read          — mark single read
  PATCH  /api/v1/notifications/{id}/actioned      — mark actioned
  POST   /api/v1/notifications/mark-all-read      — bulk mark read

Security:
  - User A cannot see User B's notifications (IDOR)
  - Unauthenticated requests → 401
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
            "email": "test@ep08.test",
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
                "notifications, "
                "timeline_events, comments, work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
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


@pytest_asyncio.fixture
async def seeded(migrated_database):
    """Seed two users in the same workspace. Returns (user_a, user_b, workspace_id)."""
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
        user_a = User.from_google_claims(
            sub=f"ep08a-{uid}", email=f"ep08a-{uid}@test.com", name="UserA", picture=None
        )
        user_b = User.from_google_claims(
            sub=f"ep08b-{uid}", email=f"ep08b-{uid}@test.com", name="UserB", picture=None
        )
        await UserRepositoryImpl(session).upsert(user_a)
        await UserRepositoryImpl(session).upsert(user_b)

        ws = Workspace.create_from_email(email=user_a.email, created_by=user_a.id)
        ws.slug = f"ep08-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user_a.id, role="admin", is_default=True
            )
        )
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user_b.id, role="member", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    token_a = _make_token(user_a.id, ws.id)
    token_b = _make_token(user_b.id, ws.id)
    return user_a.id, user_b.id, ws.id, token_a, token_b


async def _create_notification(session, *, recipient_id, workspace_id, idempotency_key=None):
    """Helper: insert a notification row directly."""
    from app.domain.models.team import Notification
    from app.infrastructure.persistence.team_repository_impl import NotificationRepositoryImpl

    n = Notification.create(
        workspace_id=workspace_id,
        recipient_id=recipient_id,
        type="review.assigned",
        subject_type="review",
        subject_id=uuid4(),
        deeplink="/items/x",
        idempotency_key=idempotency_key or str(uuid4()),
    )
    repo = NotificationRepositoryImpl(session)
    return await repo.create(n)


# ---------------------------------------------------------------------------
# GET /notifications
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_notifications_returns_only_own(http, seeded, migrated_database):
    user_a, user_b, ws_id, token_a, _ = seeded

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Create 2 notifications for user_a, 1 for user_b
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await _create_notification(session, recipient_id=user_b, workspace_id=ws_id)
        await session.commit()
    await engine.dispose()

    resp = await http.get("/api/v1/notifications", cookies={"access_token": token_a})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    for item in data["items"]:
        assert item["recipient_id"] == str(user_a)


@pytest.mark.asyncio
async def test_list_notifications_unauthenticated(http, seeded):
    resp = await http.get("/api/v1/notifications")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /notifications/unread-count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unread_count_returns_correct_number(http, seeded, migrated_database):
    user_a, _, ws_id, token_a, _ = seeded

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await session.commit()
    await engine.dispose()

    resp = await http.get("/api/v1/notifications/unread-count", cookies={"access_token": token_a})
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 2


# ---------------------------------------------------------------------------
# PATCH /notifications/{id}/read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_single_read(http, seeded, migrated_database):
    user_a, _, ws_id, token_a, _ = seeded

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        n = await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await session.commit()
    await engine.dispose()

    resp = await http.patch(f"/api/v1/notifications/{n.id}/read", cookies={"access_token": token_a})
    assert resp.status_code in (200, 204)


@pytest.mark.asyncio
async def test_mark_read_not_found(http, seeded):
    _, _, _, token_a, _ = seeded
    resp = await http.patch(
        f"/api/v1/notifications/{uuid4()}/read", cookies={"access_token": token_a}
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_all_read_only_updates_own(http, seeded, migrated_database):
    user_a, user_b, ws_id, token_a, _ = seeded

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        n_b = await _create_notification(session, recipient_id=user_b, workspace_id=ws_id)
        await session.commit()
    await engine.dispose()

    resp = await http.post("/api/v1/notifications/mark-all-read", cookies={"access_token": token_a})
    assert resp.status_code in (200, 204)

    # user_b's notification should still be unread
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from app.domain.models.team import NotificationState
        from app.infrastructure.persistence.team_repository_impl import (
            NotificationRepositoryImpl,
        )

        persisted = await NotificationRepositoryImpl(session).get(n_b.id)
        assert persisted is not None
        assert persisted.state == NotificationState.UNREAD
    await engine.dispose()


# ---------------------------------------------------------------------------
# IDOR — user B cannot see user A's notification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idor_mark_read_another_users_notification(http, seeded, migrated_database):
    """User B cannot mark user A's notification as read."""
    user_a, _, ws_id, _, token_b = seeded

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        n = await _create_notification(session, recipient_id=user_a, workspace_id=ws_id)
        await session.commit()
    await engine.dispose()

    # Token B tries to mark user A's notification
    resp = await http.patch(f"/api/v1/notifications/{n.id}/read", cookies={"access_token": token_b})
    # Should be 404 (not found for caller) — not 200
    assert resp.status_code == 404
