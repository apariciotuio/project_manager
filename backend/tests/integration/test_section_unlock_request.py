"""EP-17 — Integration tests for unlock-request endpoints.

Scenarios:
  POST /sections/{id}/lock/unlock-request
    1. No active lock → 409 NO_ACTIVE_LOCK
    2. Requester is the lock holder → 422 CANNOT_REQUEST_OWN_LOCK
    3. Happy path → 201 with LockUnlockRequest entity

  POST /sections/{id}/lock/respond
    4. Non-holder tries to respond → 403 LOCK_FORBIDDEN
    5. Request already responded → 409 ALREADY_RESPONDED
    6. Happy path accept → 200, lock released
    7. Happy path decline → 200, lock still held
    8. Unknown request_id → 404
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_UNLOCK_REQUEST_URL = "/api/v1/sections/{sid}/lock/unlock-request"
_RESPOND_URL = "/api/v1/sections/{sid}/lock/respond"
_ACQUIRE_URL = "/api/v1/sections/{sid}/lock"
_CSRF_TOKEN = "test-csrf-token-for-ep17-unlock-request-tests"


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
                "TRUNCATE TABLE "
                "lock_unlock_requests, section_locks, attachments, work_item_tags, tags, "
                "puppet_ingest_requests, puppet_sync_outbox, integration_exports, integration_configs, "
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


def _make_token(user_id, workspace_id, *, is_superadmin: bool = False) -> str:
    from app.config.settings import get_settings
    from app.infrastructure.adapters.jwt_adapter import JwtAdapter

    auth = get_settings().auth
    jwt = JwtAdapter(
        secret=auth.jwt_secret,
        issuer=auth.jwt_issuer,
        audience=auth.jwt_audience,
    )
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": f"{user_id}@test.com",
            "workspace_id": str(workspace_id),
            "is_superadmin": is_superadmin,
            "exp": int(time.time()) + 3600,
        }
    )


@pytest_asyncio.fixture
async def seeded(migrated_database):
    """Seed two users + workspace + work_item + section. Returns dict of useful IDs."""
    from app.domain.models.section import Section
    from app.domain.models.section_type import SectionType
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        # Holder user
        holder = User.from_google_claims(
            sub="unlock-holder-sub", email="holder@test.com", name="Holder", picture=None
        )
        await UserRepositoryImpl(session).upsert(holder)

        # Requester user
        requester = User.from_google_claims(
            sub="unlock-requester-sub", email="requester@test.com", name="Requester", picture=None
        )
        await UserRepositoryImpl(session).upsert(requester)

        ws = Workspace.create_from_email(email="holder@test.com", created_by=holder.id)
        ws.slug = "unlock-test"
        await WorkspaceRepositoryImpl(session).create(ws)

        for uid in (holder.id, requester.id):
            await WorkspaceMembershipRepositoryImpl(session).create(
                WorkspaceMembership.create(
                    workspace_id=ws.id, user_id=uid, role="member", is_default=True
                )
            )

        wi = WorkItem.create(
            title="Unlock test item",
            type=WorkItemType.TASK,
            owner_id=holder.id,
            creator_id=holder.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)

        section = Section.create(
            work_item_id=wi.id,
            section_type=SectionType.SUMMARY,
            display_order=1,
            is_required=True,
            created_by=holder.id,
        )
        await SectionRepositoryImpl(session).save(section)
        await session.commit()

    await engine.dispose()

    return {
        "holder_id": holder.id,
        "requester_id": requester.id,
        "workspace_id": ws.id,
        "work_item_id": wi.id,
        "section_id": section.id,
        "holder_token": _make_token(holder.id, ws.id),
        "requester_token": _make_token(requester.id, ws.id),
    }


def _auth_headers(token: str) -> dict:
    """Build headers that satisfy both auth (cookie) and CSRF (double-submit)."""
    cookie_header = f"access_token={token}; csrf_token={_CSRF_TOKEN}"
    return {
        "Cookie": cookie_header,
        "X-CSRF-Token": _CSRF_TOKEN,
    }


async def _acquire_lock(http: AsyncClient, section_id, token: str) -> None:
    url = _ACQUIRE_URL.format(sid=section_id)
    resp = await http.post(url, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# 1. No active lock → 409 NO_ACTIVE_LOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unlock_request_no_active_lock_returns_409(http, seeded):
    url = _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"])
    resp = await http.post(
        url,
        json={"reason": "Please release"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "NO_ACTIVE_LOCK"


# ---------------------------------------------------------------------------
# 2. Requester is the lock holder → 422 CANNOT_REQUEST_OWN_LOCK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unlock_request_own_lock_returns_422(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    url = _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"])
    resp = await http.post(
        url,
        json={"reason": "I want my own lock back"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "CANNOT_REQUEST_OWN_LOCK"


# ---------------------------------------------------------------------------
# 3. Happy path → 201 with LockUnlockRequest entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unlock_request_happy_path_returns_201(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    url = _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"])
    resp = await http.post(
        url,
        json={"reason": "I need to edit this section urgently"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["section_id"] == str(seeded["section_id"])
    assert data["requester_id"] == str(seeded["requester_id"])
    assert data["response"] is None
    assert data["responded_at"] is None
    assert "id" in data


# ---------------------------------------------------------------------------
# 4. Non-holder tries to respond → 403 LOCK_FORBIDDEN
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_non_holder_returns_403(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    # Create a request first
    req_resp = await http.post(
        _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"]),
        json={"reason": "Please release"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    request_id = req_resp.json()["data"]["id"]

    resp = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": request_id, "action": "accept"},
        headers=_auth_headers(seeded["requester_token"]),  # requester, not holder
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "LOCK_FORBIDDEN"


# ---------------------------------------------------------------------------
# 5. Request already responded → 409 ALREADY_RESPONDED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_already_responded_returns_409(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    req_resp = await http.post(
        _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"]),
        json={"reason": "Please release"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    request_id = req_resp.json()["data"]["id"]

    # First decline
    resp1 = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": request_id, "action": "decline", "note": "Not now"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp1.status_code == 200

    # Re-acquire lock (was not released on decline)
    # Second respond should fail with ALREADY_RESPONDED
    resp2 = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": request_id, "action": "decline"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp2.status_code == 409
    assert resp2.json()["error"]["code"] == "ALREADY_RESPONDED"


# ---------------------------------------------------------------------------
# 6. Happy path accept → 200, lock released
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_accept_releases_lock(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    req_resp = await http.post(
        _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"]),
        json={"reason": "I need to edit"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    request_id = req_resp.json()["data"]["id"]

    resp = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": request_id, "action": "accept"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["response"] == "accepted"
    assert data["responded_at"] is not None

    # Lock should now be gone — requester can acquire it
    acquire_resp = await http.post(
        _ACQUIRE_URL.format(sid=seeded["section_id"]),
        headers=_auth_headers(seeded["requester_token"]),
    )
    assert acquire_resp.status_code == 201


# ---------------------------------------------------------------------------
# 7. Happy path decline → 200, lock still held
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_decline_keeps_lock(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    req_resp = await http.post(
        _UNLOCK_REQUEST_URL.format(sid=seeded["section_id"]),
        json={"reason": "Need it now"},
        headers=_auth_headers(seeded["requester_token"]),
    )
    request_id = req_resp.json()["data"]["id"]

    resp = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": request_id, "action": "decline", "note": "Still editing"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["response"] == "declined"
    assert data["response_note"] == "Still editing"

    # Requester cannot acquire — lock still active
    acquire_resp = await http.post(
        _ACQUIRE_URL.format(sid=seeded["section_id"]),
        headers=_auth_headers(seeded["requester_token"]),
    )
    assert acquire_resp.status_code == 409


# ---------------------------------------------------------------------------
# 8. Unknown request_id → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_unknown_request_id_returns_404(http, seeded):
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])
    resp = await http.post(
        _RESPOND_URL.format(sid=seeded["section_id"]),
        json={"request_id": str(uuid4()), "action": "accept"},
        headers=_auth_headers(seeded["holder_token"]),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
