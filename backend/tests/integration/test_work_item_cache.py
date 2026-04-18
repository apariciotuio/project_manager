"""Integration tests — work_item:agg:{id} cache layer (EP-12).

Covers:
  1. GET /work-items/{id} — first call populates cache; second call hits cache (no extra DB SELECT).
  2. PATCH /work-items/{id} — evicts cache; following GET re-hits DB.
  3. Cache failure (broken client injected) — falls back to DB, no 5xx.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


def _make_token(user_id, workspace_id) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@ep12cache.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


# ---------------------------------------------------------------------------
# Spy cache — wraps FakeCache, records which keys were get/set
# ---------------------------------------------------------------------------


class SpyCache:
    """Wraps a real ICache impl; records every key accessed."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.gets: list[str] = []
        self.sets: list[str] = []
        self.deletes: list[str] = []

    async def get(self, key: str) -> str | None:
        self.gets.append(key)
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self.sets.append(key)
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
        self._store.pop(key, None)

    def reset(self) -> None:
        self.gets.clear()
        self.sets.clear()
        self.deletes.clear()


class BrokenCache:
    """Always raises — simulates cache backend failure."""

    async def get(self, key: str) -> str | None:
        raise OSError("simulated cache failure")

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        raise OSError("simulated cache failure")

    async def delete(self, key: str) -> None:
        raise OSError("simulated cache failure")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_app(cache_override):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter

    fastapi_app = _create_app()

    async def _override_cache():
        yield cache_override

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    return fastapi_app


async def _truncate(db_url: str) -> None:
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "review_responses, review_requests, "
                "validation_status, "
                "timeline_events, comments, work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()


async def _seed(db_url: str, user_id, workspace_id, work_item_id) -> None:
    """Insert the minimum rows needed to GET/PATCH a work item."""
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                INSERT INTO users (id, google_sub, email, full_name)
                VALUES (:uid, 'cache-google-sub', 'cache@test.test', 'Cache Tester')
                """
            ),
            {"uid": str(user_id)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO workspaces (id, name, slug, created_by)
                VALUES (:wid, 'Cache WS', 'cache-ws', :uid)
                """
            ),
            {"wid": str(workspace_id), "uid": str(user_id)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO workspace_memberships (user_id, workspace_id, role)
                VALUES (:uid, :wid, 'admin')
                """
            ),
            {"uid": str(user_id), "wid": str(workspace_id)},
        )
        await conn.execute(
            text(
                """
                INSERT INTO work_items (
                    id, workspace_id, project_id, type, title, state,
                    priority, creator_id, owner_id, completeness_score
                )
                VALUES (
                    :iid, :wid, :wid, 'task', 'Cache Test Item', 'draft',
                    'medium', :uid, :uid, 0
                )
                """
            ),
            {"iid": str(work_item_id), "wid": str(workspace_id), "uid": str(user_id)},
        )
    await engine.dispose()


@pytest_asyncio.fixture
async def spy_cache():
    return SpyCache()


@pytest_asyncio.fixture
async def ids():
    return {"user": uuid4(), "workspace": uuid4(), "item": uuid4()}


@pytest_asyncio.fixture
async def seeded_app(migrated_database, spy_cache, ids):
    db_url = migrated_database.database.url
    await _truncate(db_url)
    await _seed(db_url, ids["user"], ids["workspace"], ids["item"])

    fastapi_app = _build_app(spy_cache)
    yield fastapi_app

    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None


@pytest_asyncio.fixture
async def broken_app(migrated_database, ids):
    db_url = migrated_database.database.url
    await _truncate(db_url)
    await _seed(db_url, ids["user"], ids["workspace"], ids["item"])

    fastapi_app = _build_app(BrokenCache())
    yield fastapi_app

    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_work_item_populates_cache(seeded_app, spy_cache, ids):
    """First GET populates cache; second GET is served from cache (no extra set)."""
    token = _make_token(ids["user"], ids["workspace"])
    cookies = {"access_token": token}
    item_id = ids["item"]
    cache_key = f"work_item:agg:{item_id}"

    async with AsyncClient(
        transport=ASGITransport(app=seeded_app), base_url="http://test"
    ) as client:
        # First GET — cache miss → DB → set
        r1 = await client.get(f"/api/v1/work-items/{item_id}", cookies=cookies)
        assert r1.status_code == 200, r1.text
        assert cache_key in spy_cache.sets, "first GET must populate cache"

        # Record sets so far
        len(spy_cache.sets)
        spy_cache.reset()  # clear counters but NOT the store

        # Second GET — cache hit → no new set
        r2 = await client.get(f"/api/v1/work-items/{item_id}", cookies=cookies)
        assert r2.status_code == 200, r2.text
        assert cache_key in spy_cache.gets, "second GET must check cache"
        assert cache_key not in spy_cache.sets, "second GET must NOT repopulate (cache hit)"


@pytest.mark.asyncio
async def test_patch_evicts_cache(seeded_app, spy_cache, ids):
    """PATCH evicts the aggregate cache; next GET re-hits DB and re-populates."""
    token = _make_token(ids["user"], ids["workspace"])
    cookies = {"access_token": token}
    item_id = ids["item"]
    cache_key = f"work_item:agg:{item_id}"

    async with AsyncClient(
        transport=ASGITransport(app=seeded_app), base_url="http://test"
    ) as client:
        # Warm the cache
        r1 = await client.get(f"/api/v1/work-items/{item_id}", cookies=cookies)
        assert r1.status_code == 200

        spy_cache.reset()

        # PATCH — must delete the cache key
        r2 = await client.patch(
            f"/api/v1/work-items/{item_id}",
            cookies=cookies,
            json={"title": "Updated Title"},
        )
        assert r2.status_code == 200, r2.text
        assert cache_key in spy_cache.deletes, "PATCH must evict cache key"

        spy_cache.reset()

        # Next GET — cache is gone → must set again (DB read)
        r3 = await client.get(f"/api/v1/work-items/{item_id}", cookies=cookies)
        assert r3.status_code == 200
        assert cache_key in spy_cache.sets, "GET after eviction must re-populate cache"


@pytest.mark.asyncio
async def test_get_work_item_cache_failure_falls_back_to_db(broken_app, ids):
    """Broken cache: GET still returns 200 (fail-open), no 5xx."""
    token = _make_token(ids["user"], ids["workspace"])
    cookies = {"access_token": token}
    item_id = ids["item"]

    async with AsyncClient(
        transport=ASGITransport(app=broken_app), base_url="http://test"
    ) as client:
        r = await client.get(f"/api/v1/work-items/{item_id}", cookies=cookies)
        # Must not blow up — cache errors must fail-open
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["data"]["id"] == str(item_id)
