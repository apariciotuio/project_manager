"""EP-09 — Integration tests: advanced filters + cursor pagination on GET /work-items.

Tests each new filter in isolation, a combined filter scenario, and cursor traversal.
"""
from __future__ import annotations

import time
from uuid import UUID, uuid4

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
from app.main import create_app

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_LIST_URL = "/api/v1/work-items"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def app(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE ownership_history, state_transitions, work_items, "
                "workspace_memberships, sessions, oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    fastapi_app = create_app()
    yield fastapi_app

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def http(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


async def _seed(migrated_database) -> tuple[User, Workspace, str]:
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)
        user = User.from_google_claims(sub="ep09-list", email="ep09list@test.com", name="EP09", picture=None)
        await users.upsert(user)
        ws = Workspace.create_from_email(email="ep09list@test.com", created_by=user.id)
        ws.slug = "ep09-list"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(workspace_id=ws.id, user_id=user.id, role="admin", is_default=True)
        )
        await session.commit()
    await engine.dispose()

    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    token = jwt.encode({
        "sub": str(user.id),
        "email": user.email,
        "workspace_id": str(ws.id),
        "is_superadmin": False,
        "exp": int(time.time()) + 3600,
    })
    return user, ws, token


def _auth(token: str) -> dict[str, str]:
    return {"access_token": token}


async def _create_item(http: AsyncClient, token: str, **kwargs: object) -> dict:
    payload = {"title": "Test Item", "type": "task", **kwargs}
    r = await http.post(_LIST_URL, json=payload, cookies=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# Tests: auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_unauthenticated_returns_401(http: AsyncClient, migrated_database) -> None:
    r = await http.get(_LIST_URL)
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Tests: new filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_creator_id(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Created by me")
    r = await http.get(_LIST_URL, params={"creator_id": str(user.id)}, cookies=_auth(token))
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) >= 1
    assert all(i["creator_id"] == str(user.id) for i in items)


@pytest.mark.asyncio
async def test_filter_creator_id_no_match_returns_empty(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Created by me")
    other_id = str(uuid4())
    r = await http.get(_LIST_URL, params={"creator_id": other_id}, cookies=_auth(token))
    assert r.status_code == 200
    assert r.json()["data"]["items"] == []


@pytest.mark.asyncio
async def test_filter_completeness_min(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Low completeness")
    r = await http.get(
        _LIST_URL,
        params={"completeness_min": 90},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(i["completeness_score"] >= 90 for i in items)


@pytest.mark.asyncio
async def test_filter_completeness_max(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Low completeness")
    r = await http.get(
        _LIST_URL,
        params={"completeness_max": 10},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert all(i["completeness_score"] <= 10 for i in items)


@pytest.mark.asyncio
async def test_filter_priority(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="High priority item", priority="high")
    await _create_item(http, token, title="Low priority item", priority="low")
    r = await http.get(
        _LIST_URL,
        params={"priority": "high"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_filter_updated_after(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Recent item")
    r = await http.get(
        _LIST_URL,
        params={"updated_after": "2000-01-01T00:00:00Z"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["items"]) >= 1


@pytest.mark.asyncio
async def test_filter_updated_before_future(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Some item")
    r = await http.get(
        _LIST_URL,
        params={"updated_before": "2099-01-01T00:00:00Z"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()["data"]["items"]) >= 1


@pytest.mark.asyncio
async def test_filter_free_text_q(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Authentication flow")
    await _create_item(http, token, title="Database migration")
    r = await http.get(
        _LIST_URL,
        params={"q": "authentication"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert "authentication" in items[0]["title"].lower()


# ---------------------------------------------------------------------------
# Tests: sort
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sort_invalid_returns_422(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    r = await http.get(_LIST_URL, params={"sort": "nonexistent"}, cookies=_auth(token))
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_sort_title_asc(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Beta item")
    await _create_item(http, token, title="Alpha item")
    r = await http.get(_LIST_URL, params={"sort": "title_asc"}, cookies=_auth(token))
    assert r.status_code == 200
    titles = [i["title"] for i in r.json()["data"]["items"]]
    assert titles == sorted(titles)


# ---------------------------------------------------------------------------
# Tests: cursor pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cursor_pagination_traversal(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    # Create 5 items
    for i in range(5):
        await _create_item(http, token, title=f"Item {i:02d}")

    # Page 1 — limit=3
    r1 = await http.get(_LIST_URL, params={"limit": 3}, cookies=_auth(token))
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["pagination"]["has_next"] is True
    items1 = body1["data"]["items"]
    assert len(items1) == 3
    next_cursor = body1["data"]["next_cursor"]
    assert next_cursor is not None

    # Page 2 — use cursor
    r2 = await http.get(_LIST_URL, params={"limit": 3, "cursor": next_cursor}, cookies=_auth(token))
    assert r2.status_code == 200
    body2 = r2.json()
    items2 = body2["data"]["items"]
    assert len(items2) == 2
    assert body2["pagination"]["has_next"] is False

    # No overlap between pages
    ids1 = {i["id"] for i in items1}
    ids2 = {i["id"] for i in items2}
    assert ids1.isdisjoint(ids2)


@pytest.mark.asyncio
async def test_cursor_tampered_returns_422(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    r = await http.get(
        _LIST_URL,
        params={"cursor": "this-is-not-a-valid-cursor!!"},
        cookies=_auth(token),
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_limit_above_100_returns_422(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    r = await http.get(_LIST_URL, params={"limit": 101}, cookies=_auth(token))
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Tests: combined filters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_combined_state_and_priority_filter(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Draft high", priority="high")
    await _create_item(http, token, title="Draft low", priority="low")
    r = await http.get(
        _LIST_URL,
        params={"state": "draft", "priority": "high"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["priority"] == "high"


@pytest.mark.asyncio
async def test_response_shape_matches_spec(http: AsyncClient, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    await _create_item(http, token, title="Shape test item")
    r = await http.get(_LIST_URL, cookies=_auth(token))
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert "items" in body["data"]
    assert "next_cursor" in body["data"]
    assert "total" in body["data"]
    assert "pagination" in body
    assert "has_next" in body["pagination"]
    assert "total_count" in body["pagination"]
    assert "applied_filters" in body
