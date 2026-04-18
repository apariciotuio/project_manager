"""Integration tests — keyset cursor pagination for GET /api/v1/work-items.

Covers:
  - First page returns data + pagination.cursor + pagination.has_next, page_size=20
  - Supplying cursor returns next page with no duplicates
  - page_size=101 → 422
  - page_size defaults to 20 when not supplied
  - Workspace isolation: items from other workspaces never appear
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
_LIST_URL = "/api/v1/work-items"
_CSRF_TOKEN = "wi-pagination-test-csrf-token"


def _make_token(user_id: object, workspace_id: object) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@wi-pagination.test",
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
            sub=f"wi-pg-{uid}", email=f"wi-pg-{uid}@test.com", name="PgUser", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"wi-pg-{uid}"
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


async def _seed_work_items(http: AsyncClient, token: str, count: int) -> list[str]:
    """POST `count` work items via the API. Returns list of item IDs."""
    ids = []
    for i in range(count):
        resp = await http.post(
            _LIST_URL,
            json={"title": f"Test Item {i:04d}", "type": "task"},
            cookies={"access_token": token, "csrf_token": _CSRF_TOKEN},
            headers={"X-CSRF-Token": _CSRF_TOKEN},
        )
        assert resp.status_code == 201, resp.text
        ids.append(resp.json()["data"]["id"])
    return ids


# ---------------------------------------------------------------------------
# page_size=20 default — first page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_page_returns_pagination_envelope(http, seeded):
    user_id, ws_id, token = seeded
    await _seed_work_items(http, token, count=5)

    resp = await http.get(
        _LIST_URL,
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert "data" in body
    pagination = body["pagination"]
    assert "cursor" in pagination
    assert "has_next" in pagination
    assert pagination["has_next"] is False
    assert pagination["cursor"] is None


@pytest.mark.asyncio
async def test_first_page_has_next_when_more_items_exist(http, seeded):
    user_id, ws_id, token = seeded
    await _seed_work_items(http, token, count=25)

    resp = await http.get(
        _LIST_URL,
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    pagination = body["pagination"]
    assert pagination["has_next"] is True
    assert pagination["cursor"] is not None
    items = body["data"]["items"]
    assert len(items) == 20


@pytest.mark.asyncio
async def test_cursor_returns_next_page_without_duplicates(http, seeded):
    user_id, ws_id, token = seeded
    await _seed_work_items(http, token, count=25)

    # First page
    resp1 = await http.get(
        _LIST_URL,
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    cursor = body1["pagination"]["cursor"]
    page1_ids = {item["id"] for item in body1["data"]["items"]}
    assert cursor is not None

    # Second page
    resp2 = await http.get(
        _LIST_URL,
        params={"page_size": 20, "cursor": cursor},
        cookies={"access_token": token},
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    page2_ids = {item["id"] for item in body2["data"]["items"]}

    # No duplicates
    assert page1_ids.isdisjoint(page2_ids)
    # Together they cover all 25 items
    assert len(page1_ids | page2_ids) == 25
    # Second page has no further pages
    assert body2["pagination"]["has_next"] is False


@pytest.mark.asyncio
async def test_page_size_101_returns_422(http, seeded):
    _, _, token = seeded
    resp = await http.get(
        _LIST_URL,
        params={"page_size": 101},
        cookies={"access_token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_page_size_defaults_to_20(http, seeded):
    user_id, ws_id, token = seeded
    await _seed_work_items(http, token, count=25)

    # No page_size param — should default to 20
    resp = await http.get(
        _LIST_URL,
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["data"]["items"]
    pagination = body["pagination"]
    # Default 20 → 25 items → has_next=True, 20 returned
    assert len(items) == 20
    assert pagination["has_next"] is True


@pytest.mark.asyncio
async def test_workspace_isolation(http, seeded, migrated_database):
    """Items from another workspace must never appear in results."""
    user_id, ws_id, token = seeded

    # Seed 5 items in the authenticated workspace via API
    await _seed_work_items(http, token, count=5)

    # Create another workspace + user and seed items via a second HTTP client
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
        uid2 = uuid4().hex[:6]
        user2 = User.from_google_claims(
            sub=f"wi-iso-{uid2}", email=f"wi-iso-{uid2}@test.com", name="IsoUser", picture=None
        )
        await UserRepositoryImpl(session).upsert(user2)
        ws2 = Workspace.create_from_email(email=user2.email, created_by=user2.id)
        ws2.slug = f"wi-iso-{uid2}"
        await WorkspaceRepositoryImpl(session).create(ws2)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws2.id, user_id=user2.id, role="admin", is_default=True
            )
        )
        await session.commit()
        user2_id = user2.id
        ws2_id = ws2.id
    await engine.dispose()

    token2 = _make_token(user2_id, ws2_id)
    await _seed_work_items(http, token2, count=10)

    # Authenticated as ws_id user — should only see 5 items
    resp = await http.get(
        _LIST_URL,
        params={"page_size": 20},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    items = body["data"]["items"]
    assert len(items) == 5
    # Verify all items belong to the authenticated workspace
    for item in items:
        assert item["workspace_id"] == str(ws_id)
