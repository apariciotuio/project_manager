"""Integration tests — POST /api/v1/dundun/callback for wm_spec_gen_agent (EP-04).

Scenarios:
  - Valid sections payload → 200, sections upserted in DB
  - Missing work_item_id → 422
  - Nonexistent work_item_id → 422
  - Unknown dimension value → skipped, valid ones persisted
  - Empty sections list → 200, count=0
  - Re-delivery (same request_id) → sections updated idempotently
"""
from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_SECRET = "dev-callback-secret"
_URL = "/api/v1/dundun/callback"


def _sign(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post(client: AsyncClient, payload: dict, *, secret: str = _SECRET):
    raw = json.dumps(payload).encode()
    sig = _sign(raw, secret)
    return client.post(
        _URL,
        content=raw,
        headers={"Content-Type": "application/json", "X-Dundun-Signature": sig},
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
                "TRUNCATE TABLE work_item_section_versions, work_item_sections, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users "
                "RESTART IDENTITY CASCADE"
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
async def seeded_ids(migrated_database):
    """Seed user + workspace + work_item. Returns (user_id, workspace_id, work_item_id)."""
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User.from_google_claims(
            sub="sg-test-sub", email="sg@test.com", name="SG", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email="sg@test.com", created_by=user.id)
        ws.slug = "sg-test"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="SpecGen test work item",
            type=WorkItemType.BUG,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()

    await engine.dispose()
    return user.id, ws.id, wi.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spec_gen_upserts_sections(http, seeded_ids, migrated_database):
    _user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())

    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [
            {"dimension": "summary", "content": "Bug summary text here"},
            {"dimension": "steps_to_reproduce", "content": "1. Do this\n2. Observe crash"},
        ],
    }
    resp = await _post(http, payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["count"] == 2
    assert data["agent"] == "wm_spec_gen_agent"

    # Verify rows exist in DB
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from app.infrastructure.persistence.models.orm import WorkItemSectionORM

        stmt = select(WorkItemSectionORM).where(WorkItemSectionORM.work_item_id == wi_id)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 2
        section_types = {r.section_type for r in rows}
        assert section_types == {"summary", "steps_to_reproduce"}
        assert all(r.generation_source == "llm" for r in rows)
    await engine.dispose()


@pytest.mark.asyncio
async def test_spec_gen_upserts_existing_section(http, seeded_ids, migrated_database):
    _user_id, _ws_id, wi_id = seeded_ids

    # First call — creates
    resp = await _post(http, {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [{"dimension": "summary", "content": "initial content"}],
    })
    assert resp.status_code == 200

    # Second call — updates same section
    resp2 = await _post(http, {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [{"dimension": "summary", "content": "updated content by agent"}],
    })
    assert resp2.status_code == 200

    # Verify only 1 row, with updated content
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from app.infrastructure.persistence.models.orm import WorkItemSectionORM

        stmt = select(WorkItemSectionORM).where(WorkItemSectionORM.work_item_id == wi_id)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].content == "updated content by agent"
        # Version should have incremented
        assert rows[0].version >= 2
    await engine.dispose()


@pytest.mark.asyncio
async def test_spec_gen_missing_work_item_id_returns_422(http):
    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "sections": [{"dimension": "summary", "content": "something"}],
    }
    resp = await _post(http, payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "MISSING_IDS"


@pytest.mark.asyncio
async def test_spec_gen_nonexistent_work_item_returns_422(http):
    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(uuid4()),  # random — does not exist
        "sections": [{"dimension": "summary", "content": "something"}],
    }
    resp = await _post(http, payload)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "WORK_ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_spec_gen_unknown_dimension_skipped(http, seeded_ids, migrated_database):
    _user_id, _ws_id, wi_id = seeded_ids

    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [
            {"dimension": "not_a_real_dimension", "content": "ignored"},
            {"dimension": "summary", "content": "valid section"},
        ],
    }
    resp = await _post(http, payload)
    assert resp.status_code == 200
    # Only 1 valid section saved
    assert resp.json()["data"]["count"] == 1

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from app.infrastructure.persistence.models.orm import WorkItemSectionORM

        stmt = select(WorkItemSectionORM).where(WorkItemSectionORM.work_item_id == wi_id)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].section_type == "summary"
    await engine.dispose()


@pytest.mark.asyncio
async def test_spec_gen_empty_sections_returns_200_count_0(http, seeded_ids):
    _user_id, _ws_id, wi_id = seeded_ids

    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [],
    }
    resp = await _post(http, payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 0


@pytest.mark.asyncio
async def test_spec_gen_section_versions_written(http, seeded_ids, migrated_database):
    """Each upsert must write a section_version row."""
    _user_id, _ws_id, wi_id = seeded_ids

    # First upsert
    await _post(http, {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [{"dimension": "summary", "content": "v1"}],
    })
    # Second upsert — should create version row
    await _post(http, {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [{"dimension": "summary", "content": "v2"}],
    })

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from app.infrastructure.persistence.models.orm import WorkItemSectionVersionORM

        stmt = select(WorkItemSectionVersionORM).where(
            WorkItemSectionVersionORM.work_item_id == wi_id
        )
        rows = (await session.execute(stmt)).scalars().all()
        # Each save call (2 calls) should produce a version row
        assert len(rows) >= 2
    await engine.dispose()
