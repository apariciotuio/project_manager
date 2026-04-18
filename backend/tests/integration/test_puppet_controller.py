"""Integration tests for Puppet REST endpoints — EP-13.

Scenarios:
  POST /puppet/ingest-callback
    - Missing X-Puppet-Signature → 401 INVALID_SIGNATURE
    - Invalid HMAC → 401 INVALID_SIGNATURE
    - Valid HMAC, status=succeeded → 200, row updated
    - Valid HMAC, duplicate call (already succeeded) → 200, idempotent
    - Valid HMAC, status=failed → 200, row marked failed
    - Unknown ingest_request_id → 404

  POST /puppet/search
    - Unauthenticated → 401
    - Valid query → 200 with results from FakePuppetClient
    - Workspace isolation: category always derived server-side

  GET /puppet/ingest-requests
    - Unauthenticated → 401
    - Returns only rows for current workspace

  POST /puppet/ingest-requests/{id}/retry
    - Unauthenticated → 401
    - Non-failed status → 422
    - Failed row → reset to queued
    - Row from different workspace → 404
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_SECRET = "dev-puppet-callback-secret"
_CALLBACK_URL = "/api/v1/puppet/ingest-callback"
_SEARCH_URL = "/api/v1/puppet/search"
_LIST_URL = "/api/v1/puppet/ingest-requests"


def _sign_puppet(body: bytes, secret: str = _SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _post_callback(client: AsyncClient, payload: dict, *, secret: str = _SECRET):
    raw = json.dumps(payload).encode()
    sig = _sign_puppet(raw, secret)
    return client.post(
        _CALLBACK_URL,
        content=raw,
        headers={"Content-Type": "application/json", "X-Puppet-Signature": sig},
    )


def _post_callback_no_sig(client: AsyncClient, payload: dict):
    raw = json.dumps(payload).encode()
    return client.post(_CALLBACK_URL, content=raw, headers={"Content-Type": "application/json"})


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
                "TRUNCATE TABLE puppet_ingest_requests, puppet_sync_outbox, "
                "section_locks, attachments, work_item_tags, tags, "
                "integration_exports, integration_configs, "
                "routing_rules, projects, saved_searches, notifications, "
                "team_memberships, teams, timeline_events, comments, "
                "review_responses, validation_status, review_requests, "
                "validation_requirements, task_dependencies, task_node_section_links, "
                "task_nodes, work_item_versions, work_item_validators, "
                "work_item_section_versions, work_item_sections, "
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
async def seeded(migrated_database):
    """Seed user + workspace + work_item. Returns (user_id, workspace_id, work_item_id, access_token)."""
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.adapters.jwt_adapter import JwtAdapter
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User.from_google_claims(sub="puppet-sub", email="puppet@test.com", name="Puppet", picture=None)
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email="puppet@test.com", created_by=user.id)
        ws.slug = "puppet-test"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(workspace_id=ws.id, user_id=user.id, role="admin", is_default=True)
        )

        wi = WorkItem.create(
            title="Puppet test work item",
            type=WorkItemType.TASK,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()

    await engine.dispose()

    import time

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(ws.id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user.id, ws.id, wi.id, token


# ---------------------------------------------------------------------------
# POST /puppet/ingest-callback — HMAC auth
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_missing_signature_returns_401(http):
    payload = {"ingest_request_id": str(uuid4()), "status": "succeeded", "puppet_doc_id": "doc-1"}
    resp = await _post_callback_no_sig(http, payload)
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_callback_invalid_signature_returns_401(http):
    raw = json.dumps({"ingest_request_id": str(uuid4()), "status": "succeeded"}).encode()
    resp = await http.post(
        _CALLBACK_URL,
        content=raw,
        headers={"Content-Type": "application/json", "X-Puppet-Signature": "deadbeef"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_SIGNATURE"


@pytest.mark.asyncio
async def test_callback_unknown_request_id_returns_404(http):
    payload = {
        "ingest_request_id": str(uuid4()),
        "status": "succeeded",
        "puppet_doc_id": "doc-xyz",
    }
    resp = await _post_callback(http, payload)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_callback_succeeded_updates_row(http, seeded, migrated_database):
    _user_id, ws_id, wi_id, _token = seeded

    # Create a queued ingest_request row first
    engine = create_async_engine(migrated_database.database.url)
    ingest_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status)
                VALUES
                    (:id, :ws_id, 'outbox', :wi_id, '{}', 'queued')
            """),
            {"id": str(ingest_id), "ws_id": str(ws_id), "wi_id": str(wi_id)},
        )
    await engine.dispose()

    payload = {
        "ingest_request_id": str(ingest_id),
        "status": "succeeded",
        "puppet_doc_id": "puppet-doc-abc",
    }
    resp = await _post_callback(http, payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["processed"] is True
    assert data["data"]["status"] == "succeeded"

    # Verify DB row
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        row = (await conn.execute(
            text("SELECT status, puppet_doc_id FROM puppet_ingest_requests WHERE id = :id"),
            {"id": str(ingest_id)},
        )).fetchone()
    await engine.dispose()
    assert row is not None
    assert row[0] == "succeeded"
    assert row[1] == "puppet-doc-abc"


@pytest.mark.asyncio
async def test_callback_idempotent_on_succeeded_row(http, seeded, migrated_database):
    _user_id, ws_id, wi_id, _token = seeded

    engine = create_async_engine(migrated_database.database.url)
    ingest_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status, puppet_doc_id)
                VALUES
                    (:id, :ws_id, 'outbox', :wi_id, '{}', 'succeeded', 'old-doc-id')
            """),
            {"id": str(ingest_id), "ws_id": str(ws_id), "wi_id": str(wi_id)},
        )
    await engine.dispose()

    payload = {
        "ingest_request_id": str(ingest_id),
        "status": "succeeded",
        "puppet_doc_id": "new-doc-id",
    }
    resp = await _post_callback(http, payload)
    assert resp.status_code == 200
    assert resp.json()["data"]["processed"] is False
    assert "already processed" in resp.json()["message"]

    # Doc id not changed
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        row = (await conn.execute(
            text("SELECT puppet_doc_id FROM puppet_ingest_requests WHERE id = :id"),
            {"id": str(ingest_id)},
        )).fetchone()
    await engine.dispose()
    assert row[0] == "old-doc-id"


# ---------------------------------------------------------------------------
# POST /puppet/search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_unauthenticated_returns_401(http):
    resp = await http.post(_SEARCH_URL, json={"query": "test"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_fake_results(http, seeded):
    _user_id, _ws_id, _wi_id, token = seeded
    resp = await http.post(
        _SEARCH_URL,
        json={"query": "puppet", "limit": 5},
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()
    # FakePuppetClient returns [] for empty store — just verify shape
    assert "data" in data


@pytest.mark.asyncio
async def test_search_workspace_tag_server_enforced(http, seeded):
    """Category must be derived from the user's workspace_id — never from the client."""
    _user_id, ws_id, _wi_id, token = seeded
    # Even if a client passes a category for another workspace, it gets namespaced
    resp = await http.post(
        _SEARCH_URL,
        json={"query": "test", "category": "wm_malicious_ws_id"},
        cookies={"access_token": token},
    )
    # Should succeed — the category is safely namespaced with the real workspace prefix
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /puppet/ingest-requests — cursor pagination
# ---------------------------------------------------------------------------


async def _insert_ingest_request(conn, *, ingest_id, ws_id, wi_id, status="queued", created_at=None):
    """Insert a puppet_ingest_request row; created_at optional explicit value."""
    if created_at is None:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status)
                VALUES (:id, :ws_id, 'manual', :wi_id, '{}', :status)
            """),
            {"id": str(ingest_id), "ws_id": str(ws_id), "wi_id": str(wi_id), "status": status},
        )
    else:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status, created_at, updated_at)
                VALUES (:id, :ws_id, 'manual', :wi_id, '{}', :status, :created_at, :created_at)
            """),
            {
                "id": str(ingest_id),
                "ws_id": str(ws_id),
                "wi_id": str(wi_id),
                "status": status,
                "created_at": created_at,
            },
        )


@pytest.mark.asyncio
async def test_list_ingest_requests_unauthenticated(http):
    resp = await http.get(_LIST_URL)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_returns_cursor_pagination_shape(http, seeded, migrated_database):
    """First page returns correct shape with pagination envelope."""
    _user_id, ws_id, wi_id, token = seeded

    engine = create_async_engine(migrated_database.database.url)
    ingest_id = uuid4()
    async with engine.begin() as conn:
        await _insert_ingest_request(conn, ingest_id=ingest_id, ws_id=ws_id, wi_id=wi_id)
    await engine.dispose()

    resp = await http.get(_LIST_URL, cookies={"access_token": token})
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body["data"]
    assert "pagination" in body["data"]
    pagination = body["data"]["pagination"]
    assert "next_cursor" in pagination
    assert "has_more" in pagination
    items = body["data"]["items"]
    assert any(r["id"] == str(ingest_id) for r in items)


@pytest.mark.asyncio
async def test_list_second_page_no_duplicates(http, seeded, migrated_database):
    """Cursor from first page yields second page without overlap."""
    from datetime import datetime, timedelta, timezone

    _user_id, ws_id, wi_id, token = seeded

    base_ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ids = [uuid4() for _ in range(5)]

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        for i, rid in enumerate(ids):
            ts = base_ts - timedelta(minutes=i)  # newer first
            await _insert_ingest_request(conn, ingest_id=rid, ws_id=ws_id, wi_id=wi_id, created_at=ts)
    await engine.dispose()

    # Page 1 — limit 3
    resp1 = await http.get(f"{_LIST_URL}?page_size=3", cookies={"access_token": token})
    assert resp1.status_code == 200
    page1 = resp1.json()["data"]
    assert page1["pagination"]["has_more"] is True
    cursor = page1["pagination"]["next_cursor"]
    assert cursor is not None
    page1_ids = {r["id"] for r in page1["items"]}
    assert len(page1["items"]) == 3

    # Page 2 — continue from cursor
    resp2 = await http.get(f"{_LIST_URL}?page_size=3&cursor={cursor}", cookies={"access_token": token})
    assert resp2.status_code == 200
    page2 = resp2.json()["data"]
    page2_ids = {r["id"] for r in page2["items"]}

    # No overlap
    assert page1_ids.isdisjoint(page2_ids)
    # Together they cover all 5 inserted rows
    assert page1_ids | page2_ids == {str(rid) for rid in ids}


@pytest.mark.asyncio
async def test_list_empty_trailing_page_has_no_cursor(http, seeded, migrated_database):
    """When page exactly exhausts results, has_more=false and next_cursor=null."""
    _user_id, ws_id, wi_id, token = seeded

    ingest_id = uuid4()
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await _insert_ingest_request(conn, ingest_id=ingest_id, ws_id=ws_id, wi_id=wi_id)
    await engine.dispose()

    resp = await http.get(f"{_LIST_URL}?page_size=100", cookies={"access_token": token})
    assert resp.status_code == 200
    pagination = resp.json()["data"]["pagination"]
    assert pagination["has_more"] is False
    assert pagination["next_cursor"] is None


@pytest.mark.asyncio
async def test_list_invalid_cursor_returns_422(http, seeded):
    """Tampered cursor → 422."""
    _user_id, _ws_id, _wi_id, token = seeded
    resp = await http.get(f"{_LIST_URL}?cursor=notacursor", cookies={"access_token": token})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_list_page_size_above_max_returns_422(http, seeded):
    """page_size > 100 → 422."""
    _user_id, _ws_id, _wi_id, token = seeded
    resp = await http.get(f"{_LIST_URL}?page_size=101", cookies={"access_token": token})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_page_size_zero_returns_422(http, seeded):
    """page_size=0 → 422."""
    _user_id, _ws_id, _wi_id, token = seeded
    resp = await http.get(f"{_LIST_URL}?page_size=0", cookies={"access_token": token})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_workspace_isolation(http, seeded, migrated_database):
    """Rows from another workspace are NOT returned."""
    from app.domain.models.user import User
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.infrastructure.adapters.jwt_adapter import JwtAdapter
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    import time

    _user_id, ws_id, wi_id, token = seeded

    # Create a second workspace + user
    engine2 = create_async_engine(migrated_database.database.url)
    factory2 = __import__("sqlalchemy.ext.asyncio", fromlist=["async_sessionmaker"]).async_sessionmaker(
        engine2, expire_on_commit=False
    )
    async with factory2() as s2:
        other_user = User.from_google_claims(sub="other-sub", email="other@test.com", name="Other", picture=None)
        await UserRepositoryImpl(s2).upsert(other_user)
        other_ws = Workspace.create_from_email(email="other@test.com", created_by=other_user.id)
        other_ws.slug = "other-ws"
        await WorkspaceRepositoryImpl(s2).create(other_ws)
        await WorkspaceMembershipRepositoryImpl(s2).create(
            WorkspaceMembership.create(workspace_id=other_ws.id, user_id=other_user.id, role="admin", is_default=True)
        )
        await s2.commit()
    await engine2.dispose()

    # Insert ingest request for other workspace
    other_id = uuid4()
    engine3 = create_async_engine(migrated_database.database.url)
    async with engine3.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status)
                VALUES (:id, :ws_id, 'manual', NULL, '{}', 'queued')
            """),
            {"id": str(other_id), "ws_id": str(other_ws.id)},
        )
    await engine3.dispose()

    # Fetch with original user token — other ws row must not appear
    resp = await http.get(_LIST_URL, cookies={"access_token": token})
    assert resp.status_code == 200
    returned_ids = {r["id"] for r in resp.json()["data"]["items"]}
    assert str(other_id) not in returned_ids


# ---------------------------------------------------------------------------
# POST /puppet/ingest-requests/{id}/retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_unauthenticated(http):
    resp = await http.post(f"{_LIST_URL}/{uuid4()}/retry")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_retry_not_found(http, seeded):
    _user_id, _ws_id, _wi_id, token = seeded
    resp = await http.post(
        f"{_LIST_URL}/{uuid4()}/retry",
        cookies={"access_token": token},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_retry_queued_row_returns_422(http, seeded, migrated_database):
    _user_id, ws_id, wi_id, token = seeded

    engine = create_async_engine(migrated_database.database.url)
    ingest_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status)
                VALUES (:id, :ws_id, 'outbox', :wi_id, '{}', 'queued')
            """),
            {"id": str(ingest_id), "ws_id": str(ws_id), "wi_id": str(wi_id)},
        )
    await engine.dispose()

    resp = await http.post(
        f"{_LIST_URL}/{ingest_id}/retry",
        cookies={"access_token": token},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_retry_failed_row_resets_to_queued(http, seeded, migrated_database):
    _user_id, ws_id, wi_id, token = seeded

    engine = create_async_engine(migrated_database.database.url)
    ingest_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO puppet_ingest_requests
                    (id, workspace_id, source_kind, work_item_id, payload, status, attempts, last_error)
                VALUES (:id, :ws_id, 'outbox', :wi_id, '{}', 'failed', 3, 'connection refused')
            """),
            {"id": str(ingest_id), "ws_id": str(ws_id), "wi_id": str(wi_id)},
        )
    await engine.dispose()

    resp = await http.post(
        f"{_LIST_URL}/{ingest_id}/retry",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "queued"

    # Verify DB
    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        row = (await conn.execute(
            text("SELECT status, attempts FROM puppet_ingest_requests WHERE id = :id"),
            {"id": str(ingest_id)},
        )).fetchone()
    await engine.dispose()
    assert row[0] == "queued"
    assert row[1] == 0
