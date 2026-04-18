"""Integration tests — filter params restored for GET /api/v1/work-items.

Covers:
  - ?q=foo returns only items whose title matches
  - ?creator_id=<uuid> filters correctly
  - Filter + cursor combined returns consistent pages without duplicates
  - ?sort=title_asc overrides default keyset order (keyset on title,id)
  - Sort + cursor combined (title_asc) returns consistent pages
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
_CSRF_TOKEN = "wi-filter-pagination-test-csrf-token"


def _make_token(user_id: object, workspace_id: object) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@wi-filter-pagination.test",
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
    """Seed two users (creator1, creator2) in the same workspace. Returns dict."""
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

        user1 = User.from_google_claims(
            sub=f"wi-fp-{uid}-1", email=f"wi-fp-{uid}-1@test.com", name="User1", picture=None
        )
        user2 = User.from_google_claims(
            sub=f"wi-fp-{uid}-2", email=f"wi-fp-{uid}-2@test.com", name="User2", picture=None
        )
        repo = UserRepositoryImpl(session)
        await repo.upsert(user1)
        await repo.upsert(user2)

        ws = Workspace.create_from_email(email=user1.email, created_by=user1.id)
        ws.slug = f"wi-fp-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        mem_repo = WorkspaceMembershipRepositoryImpl(session)
        await mem_repo.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user1.id, role="admin", is_default=True
            )
        )
        await mem_repo.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user2.id, role="member", is_default=False
            )
        )
        await session.commit()
    await engine.dispose()

    token1 = _make_token(user1.id, ws.id)
    token2 = _make_token(user2.id, ws.id)
    return {
        "user1_id": user1.id,
        "user2_id": user2.id,
        "ws_id": ws.id,
        "token1": token1,
        "token2": token2,
    }


async def _create_item(http: AsyncClient, token: str, title: str) -> str:
    resp = await http.post(
        _LIST_URL,
        json={"title": title, "type": "task"},
        cookies={"access_token": token, "csrf_token": _CSRF_TOKEN},
        headers={"X-CSRF-Token": _CSRF_TOKEN},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------------------
# q filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_q_filter_returns_matching_items_only(http, seeded):
    token1 = seeded["token1"]
    await _create_item(http, token1, "Alpha task")
    await _create_item(http, token1, "Beta task")
    await _create_item(http, token1, "Alpha issue")

    resp = await http.get(
        _LIST_URL,
        params={"q": "Alpha"},
        cookies={"access_token": token1},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    for item in items:
        assert "Alpha" in item["title"]


@pytest.mark.asyncio
async def test_q_filter_no_match_returns_empty(http, seeded):
    token1 = seeded["token1"]
    await _create_item(http, token1, "Alpha task")

    resp = await http.get(
        _LIST_URL,
        params={"q": "ZZZnonexistent"},
        cookies={"access_token": token1},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 0


# ---------------------------------------------------------------------------
# creator_id filter
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creator_id_filter_returns_only_that_creator_items(http, seeded):
    token1, token2 = seeded["token1"], seeded["token2"]
    user1_id, user2_id = seeded["user1_id"], seeded["user2_id"]

    await _create_item(http, token1, "User1 item A")
    await _create_item(http, token1, "User1 item B")
    await _create_item(http, token2, "User2 item")

    resp = await http.get(
        _LIST_URL,
        params={"creator_id": str(user1_id)},
        cookies={"access_token": token1},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    for item in items:
        assert item["creator_id"] == str(user1_id)


@pytest.mark.asyncio
async def test_creator_id_filter_other_creator_returns_empty(http, seeded):
    token1, token2 = seeded["token1"], seeded["token2"]
    user2_id = seeded["user2_id"]

    # Only user1 creates items; filter by user2
    await _create_item(http, token1, "User1 item A")
    await _create_item(http, token1, "User1 item B")

    resp = await http.get(
        _LIST_URL,
        params={"creator_id": str(user2_id)},
        cookies={"access_token": token1},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert len(items) == 0


# ---------------------------------------------------------------------------
# filter + cursor combined
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creator_id_filter_with_cursor_no_duplicates(http, seeded):
    token1, token2 = seeded["token1"], seeded["token2"]
    user1_id = seeded["user1_id"]

    # 25 items by user1, 5 by user2 (noise)
    for i in range(25):
        await _create_item(http, token1, f"U1-{i:04d}")
    for i in range(5):
        await _create_item(http, token2, f"U2-{i:04d}")

    # Page 1
    resp1 = await http.get(
        _LIST_URL,
        params={"creator_id": str(user1_id), "page_size": 20},
        cookies={"access_token": token1},
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    page1_ids = {item["id"] for item in body1["data"]["items"]}
    cursor = body1["pagination"]["cursor"]
    assert body1["pagination"]["has_next"] is True
    assert cursor is not None
    assert len(page1_ids) == 20

    # Page 2
    resp2 = await http.get(
        _LIST_URL,
        params={"creator_id": str(user1_id), "page_size": 20, "cursor": cursor},
        cookies={"access_token": token1},
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    page2_ids = {item["id"] for item in body2["data"]["items"]}

    assert page1_ids.isdisjoint(page2_ids)
    assert len(page1_ids | page2_ids) == 25
    assert body2["pagination"]["has_next"] is False

    # All items are user1's
    for item in body2["data"]["items"]:
        assert item["creator_id"] == str(user1_id)


# ---------------------------------------------------------------------------
# sort override
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sort_title_asc_returns_items_in_title_order(http, seeded):
    token1 = seeded["token1"]
    await _create_item(http, token1, "Zebra")
    await _create_item(http, token1, "Apple")
    await _create_item(http, token1, "Mango")

    resp = await http.get(
        _LIST_URL,
        params={"sort": "title_asc"},
        cookies={"access_token": token1},
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    titles = [i["title"] for i in items]
    assert titles == sorted(titles)


@pytest.mark.asyncio
async def test_sort_title_asc_with_cursor_no_duplicates(http, seeded):
    token1 = seeded["token1"]
    for i in range(25):
        await _create_item(http, token1, f"Item-{chr(65 + i % 26)}-{i:04d}")

    resp1 = await http.get(
        _LIST_URL,
        params={"sort": "title_asc", "page_size": 20},
        cookies={"access_token": token1},
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    page1_ids = {item["id"] for item in body1["data"]["items"]}
    cursor = body1["pagination"]["cursor"]
    assert body1["pagination"]["has_next"] is True
    assert len(page1_ids) == 20

    resp2 = await http.get(
        _LIST_URL,
        params={"sort": "title_asc", "page_size": 20, "cursor": cursor},
        cookies={"access_token": token1},
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    page2_ids = {item["id"] for item in body2["data"]["items"]}

    assert page1_ids.isdisjoint(page2_ids)
    assert len(page1_ids | page2_ids) == 25
