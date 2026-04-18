"""Integration tests — cursor-based pagination for GET /api/v1/notifications.

Covers:
  - First page returns data + pagination.cursor + pagination.has_next
  - Supplying cursor returns next page without duplicates
  - page_size=101 → 422
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

_JWT_SECRET = "yoda-dev-secret-key-minimum-32-bytes-long!!"


def _make_token(user_id: object, workspace_id: object) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@inbox-pagination.test",
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
    """Seed one user in a workspace. Returns (user_id, workspace_id, token)."""
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
        user = User.from_google_claims(
            sub=f"inbox-pg-{uid}", email=f"inbox-pg-{uid}@test.com", name="PgUser", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"inbox-pg-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    return user.id, ws.id, token


async def _seed_notifications(migrated_database, *, recipient_id, workspace_id, count: int):
    """Insert `count` notifications and return their IDs in insertion order."""
    from app.domain.models.team import Notification
    from app.infrastructure.persistence.team_repository_impl import NotificationRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    ids = []
    async with factory() as session:
        for _ in range(count):
            n = Notification.create(
                workspace_id=workspace_id,
                recipient_id=recipient_id,
                type="review.assigned",
                subject_type="review",
                subject_id=uuid4(),
                deeplink="/items/x",
                idempotency_key=str(uuid4()),
            )
            created = await NotificationRepositoryImpl(session).create(n)
            ids.append(created.id)
        await session.commit()
    await engine.dispose()
    return ids


# ---------------------------------------------------------------------------
# First page returns data + pagination envelope
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_page_returns_pagination_envelope(http, seeded, migrated_database):
    user_id, ws_id, token = seeded
    await _seed_notifications(migrated_database, recipient_id=user_id, workspace_id=ws_id, count=5)

    resp = await http.get(
        "/api/v1/notifications",
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    items = body["data"]["items"]
    pagination = body["data"]["pagination"]

    assert len(items) == 5
    assert "cursor" in pagination
    assert "has_next" in pagination
    assert pagination["has_next"] is False
    assert pagination["cursor"] is None


@pytest.mark.asyncio
async def test_first_page_has_next_when_more_items_exist(http, seeded, migrated_database):
    user_id, ws_id, token = seeded
    await _seed_notifications(migrated_database, recipient_id=user_id, workspace_id=ws_id, count=25)

    resp = await http.get(
        "/api/v1/notifications",
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    body = resp.json()
    pagination = body["data"]["pagination"]

    assert pagination["has_next"] is True
    assert pagination["cursor"] is not None
    assert len(body["data"]["items"]) == 20


@pytest.mark.asyncio
async def test_cursor_returns_next_page_without_duplicates(http, seeded, migrated_database):
    user_id, ws_id, token = seeded
    await _seed_notifications(migrated_database, recipient_id=user_id, workspace_id=ws_id, count=25)

    # First page
    resp1 = await http.get(
        "/api/v1/notifications",
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp1.status_code == 200
    page1 = resp1.json()["data"]
    cursor = page1["pagination"]["cursor"]
    page1_ids = {item["id"] for item in page1["items"]}
    assert cursor is not None

    # Second page
    resp2 = await http.get(
        "/api/v1/notifications",
        params={"page_size": 20, "cursor": cursor},
        cookies={"access_token": token},
    )
    assert resp2.status_code == 200
    page2 = resp2.json()["data"]
    page2_ids = {item["id"] for item in page2["items"]}

    # No duplicates
    assert page1_ids.isdisjoint(page2_ids)
    # Together they cover all 25 items
    assert len(page1_ids | page2_ids) == 25
    # Second page has no more items
    assert page2["pagination"]["has_next"] is False


@pytest.mark.asyncio
async def test_page_size_above_100_returns_422(http, seeded):
    _, _, token = seeded
    resp = await http.get(
        "/api/v1/notifications",
        params={"page_size": 101},
        cookies={"access_token": token},
    )
    assert resp.status_code == 422
