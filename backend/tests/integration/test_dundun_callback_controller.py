"""Integration tests for POST /api/v1/dundun/callback — EP-03 Phase 3b.

Scenarios:
  - Missing X-Dundun-Signature header → 401
  - Invalid HMAC → 401
  - Valid HMAC, wm_suggestion_agent, status=success, 2 suggestions → 200, 2 rows in DB
  - Valid HMAC, wm_suggestion_agent, duplicate request_id → 200, idempotent (no new rows)
  - Valid HMAC, wm_gap_agent, status=success, 3 findings → 200, 3 rows in DB
  - Valid HMAC, wm_gap_agent, retry with same request_id → 200, idempotent
  - Valid HMAC, wm_quick_action_agent → 501
  - Valid HMAC, status=error → 200, nothing persisted, error logged
"""
from __future__ import annotations

import hashlib
import hmac
import json
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _post_no_sig(client: AsyncClient, payload: dict):
    raw = json.dumps(payload).encode()
    return client.post(_URL, content=raw, headers={"Content-Type": "application/json"})


def _post_bad_sig(client: AsyncClient, payload: dict):
    raw = json.dumps(payload).encode()
    return client.post(
        _URL,
        content=raw,
        headers={"Content-Type": "application/json", "X-Dundun-Signature": "deadbeef"},
    )


# ---------------------------------------------------------------------------
# Fixtures — use the migrated_database + create an isolated app per test module
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
                "TRUNCATE TABLE gap_findings, assistant_suggestions, conversation_threads, "
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
        user = User.from_google_claims(sub="cb-test-sub", email="cb@test.com", name="CB", picture=None)
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email="cb@test.com", created_by=user.id)
        ws.slug = "cb-test"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(workspace_id=ws.id, user_id=user.id, role="admin", is_default=True)
        )

        wi = WorkItem.create(
            title="Callback test work item",
            type=WorkItemType.TASK,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()

    await engine.dispose()
    return user.id, ws.id, wi.id


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_signature_returns_401(http):
    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "user_id": str(uuid4()),
        "suggestions": [],
    }
    resp = await _post_no_sig(http, payload)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(http):
    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(uuid4()),
        "batch_id": str(uuid4()),
        "user_id": str(uuid4()),
        "suggestions": [],
    }
    resp = await _post_bad_sig(http, payload)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


# ---------------------------------------------------------------------------
# wm_suggestion_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suggestion_callback_persists_two_rows(http, seeded_ids, migrated_database):
    user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())
    batch_id = str(uuid4())

    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "batch_id": batch_id,
        "user_id": str(user_id),
        "suggestions": [
            {
                "section_id": None,
                "proposed_content": "New description A",
                "current_content": "Old description",
                "rationale": "Better clarity",
            },
            {
                "section_id": None,
                "proposed_content": "New description B",
                "current_content": "Old description",
                "rationale": None,
            },
        ],
    }

    resp = await _post(http, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["processed"] is True
    assert data["data"]["count"] == 2
    assert data["data"]["agent"] == "wm_suggestion_agent"

    # Verify DB rows
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM assistant_suggestions WHERE dundun_request_id = :rid"),
            {"rid": request_id},
        )
        count = result.scalar()
    await engine.dispose()
    assert count == 2


@pytest.mark.asyncio
async def test_suggestion_callback_idempotent_on_retry(http, seeded_ids, migrated_database):
    user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())
    batch_id = str(uuid4())

    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "batch_id": batch_id,
        "user_id": str(user_id),
        "suggestions": [
            {
                "section_id": None,
                "proposed_content": "Proposed content",
                "current_content": "Current content",
                "rationale": None,
            }
        ],
    }

    resp1 = await _post(http, payload)
    assert resp1.status_code == 200
    assert resp1.json()["data"]["count"] == 1

    # Retry — same request_id
    resp2 = await _post(http, payload)
    assert resp2.status_code == 200
    assert "already processed" in resp2.json()["message"]

    # Still only 1 row
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM assistant_suggestions WHERE dundun_request_id = :rid"),
            {"rid": request_id},
        )
        count = result.scalar()
    await engine.dispose()
    assert count == 1


# ---------------------------------------------------------------------------
# wm_gap_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gap_callback_persists_three_findings(http, seeded_ids, migrated_database):
    _user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())

    payload = {
        "agent": "wm_gap_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "gap_findings": [
            {"dimension": "description", "severity": "blocking", "message": "Description too short"},
            {"dimension": "acceptance_criteria", "severity": "warning", "message": "No AC found"},
            {"dimension": "title", "severity": "info", "message": "Title could be clearer"},
        ],
    }

    resp = await _post(http, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["count"] == 3
    assert data["data"]["agent"] == "wm_gap_agent"

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM gap_findings "
                "WHERE work_item_id = :wid AND source = 'dundun' AND invalidated_at IS NULL"
            ),
            {"wid": str(wi_id)},
        )
        count = result.scalar()
    await engine.dispose()
    assert count == 3


@pytest.mark.asyncio
async def test_gap_callback_idempotent_on_retry(http, seeded_ids, migrated_database):
    _user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())

    payload = {
        "agent": "wm_gap_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(wi_id),
        "gap_findings": [
            {"dimension": "description", "severity": "blocking", "message": "Too short"},
        ],
    }

    resp1 = await _post(http, payload)
    assert resp1.status_code == 200
    assert resp1.json()["data"]["count"] == 1

    # Retry — same request_id: idempotent, no new rows
    resp2 = await _post(http, payload)
    assert resp2.status_code == 200
    assert "already processed" in resp2.json()["message"]

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT COUNT(*) FROM gap_findings "
                "WHERE work_item_id = :wid AND dundun_request_id = :rid AND invalidated_at IS NULL"
            ),
            {"wid": str(wi_id), "rid": request_id},
        )
        count = result.scalar()
    await engine.dispose()
    assert count == 1


# ---------------------------------------------------------------------------
# wm_quick_action_agent — deferred
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_quick_action_returns_501(http):
    payload = {
        "agent": "wm_quick_action_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(uuid4()),
        "quick_action_result": {"section_id": None, "new_content": "Rewritten"},
    }
    resp = await _post(http, payload)
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# status=error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_error_status_returns_200_nothing_persisted(http, seeded_ids, migrated_database, caplog):
    user_id, _ws_id, wi_id = seeded_ids
    request_id = str(uuid4())

    payload = {
        "agent": "wm_suggestion_agent",
        "request_id": request_id,
        "status": "error",
        "work_item_id": str(wi_id),
        "error_message": "Dundun internal timeout",
    }

    import logging

    with caplog.at_level(logging.WARNING, logger="app.presentation.controllers.dundun_callback_controller"):
        resp = await _post(http, payload)

    assert resp.status_code == 200
    assert resp.json()["data"]["count"] == 0

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT COUNT(*) FROM assistant_suggestions WHERE dundun_request_id = :rid"),
            {"rid": request_id},
        )
        count = result.scalar()
    await engine.dispose()
    assert count == 0
    assert any("Dundun internal timeout" in r.message or request_id in r.message for r in caplog.records)
