"""Integration tests — EP-04 REST controllers.

Covers:
  GET  /api/v1/work-items/{id}/specification     — list sections
  PATCH /api/v1/work-items/{id}/sections/{sid}   — update section
  GET  /api/v1/work-items/{id}/completeness      — score + dims
  GET  /api/v1/work-items/{id}/gaps              — gap list
  GET  /api/v1/work-items/{id}/next-step         — next action

Auth: JWT in cookie. Workspace-scoped sessions. FakeCache for Redis.
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


def _make_token(user_id, workspace_id) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@ep04.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


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
                "TRUNCATE TABLE work_item_section_versions, work_item_sections, "
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
    fastapi_app._fake_cache = fake_cache  # type: ignore[attr-defined]
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
    """Seed user + workspace + work_item. Returns (user_id, workspace_id, work_item_id, token)."""
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
        uid = uuid4().hex[:6]
        user = User.from_google_claims(
            sub=f"ep04-{uid}", email=f"ep04-{uid}@test.com", name="EP04", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"ep04-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="EP-04 test item",
            type=WorkItemType.BUG,
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    return user.id, ws.id, wi.id, token


def _auth(token: str) -> dict:
    return {"cookies": {"access_token": token}}


# ---------------------------------------------------------------------------
# GET /specification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_specification_empty(http, seeded):
    _, _, wi_id, token = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/specification", cookies={"access_token": token})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["work_item_id"] == str(wi_id)
    assert data["sections"] == []


@pytest.mark.asyncio
async def test_get_specification_unauthenticated(http, seeded):
    _, _, wi_id, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/specification")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_specification_with_sections(http, seeded, migrated_database):
    _, _, wi_id, token = seeded

    # Seed sections via spec-gen callback
    from tests.integration.test_spec_gen_callback import _sign
    import json, hashlib, hmac as _hmac

    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [
            {"dimension": "summary", "content": "Bug summary here"},
            {"dimension": "actual_behavior", "content": "App crashes"},
        ],
    }
    raw = json.dumps(payload).encode()
    sig = _hmac.new(b"dev-callback-secret", raw, hashlib.sha256).hexdigest()
    cb_resp = await http.post(
        "/api/v1/dundun/callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dundun-Signature": sig},
    )
    assert cb_resp.status_code == 200

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/specification",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    sections = resp.json()["data"]["sections"]
    assert len(sections) == 2
    section_types = {s["section_type"] for s in sections}
    assert section_types == {"summary", "actual_behavior"}


# ---------------------------------------------------------------------------
# PATCH /sections/{section_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_section_updates_content(http, seeded, migrated_database):
    user_id, _, wi_id, token = seeded

    # Bootstrap sections first
    from tests.integration.test_spec_gen_callback import _sign
    import json, hashlib, hmac as _hmac

    payload = {
        "agent": "wm_spec_gen_agent",
        "request_id": str(uuid4()),
        "status": "success",
        "work_item_id": str(wi_id),
        "sections": [{"dimension": "summary", "content": "original"}],
    }
    raw = json.dumps(payload).encode()
    sig = _hmac.new(b"dev-callback-secret", raw, hashlib.sha256).hexdigest()
    await http.post(
        "/api/v1/dundun/callback",
        content=raw,
        headers={"Content-Type": "application/json", "X-Dundun-Signature": sig},
    )

    # Get the section id
    spec_resp = await http.get(
        f"/api/v1/work-items/{wi_id}/specification",
        cookies={"access_token": token},
    )
    sections = spec_resp.json()["data"]["sections"]
    assert len(sections) == 1
    section_id = sections[0]["id"]
    original_version = sections[0]["version"]

    # Patch it
    patch_resp = await http.patch(
        f"/api/v1/work-items/{wi_id}/sections/{section_id}",
        json={"content": "updated by owner"},
        cookies={"access_token": token},
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()["data"]
    assert updated["content"] == "updated by owner"
    assert updated["generation_source"] == "manual"
    assert updated["version"] == original_version + 1


@pytest.mark.asyncio
async def test_patch_section_nonexistent_returns_404(http, seeded):
    _, _, wi_id, token = seeded
    resp = await http.patch(
        f"/api/v1/work-items/{wi_id}/sections/{uuid4()}",
        json={"content": "something"},
        cookies={"access_token": token},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_section_unauthenticated_returns_401(http, seeded, migrated_database):
    _, _, wi_id, _ = seeded
    resp = await http.patch(
        f"/api/v1/work-items/{wi_id}/sections/{uuid4()}",
        json={"content": "something"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_completeness_returns_score(http, seeded):
    _, _, wi_id, token = seeded
    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/completeness",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "score" in data
    assert "level" in data
    assert "dimensions" in data
    assert "cached" in data
    assert 0 <= data["score"] <= 100


@pytest.mark.asyncio
async def test_get_completeness_unauthenticated_returns_401(http, seeded):
    _, _, wi_id, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/completeness")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_completeness_nonexistent_returns_404(http, seeded):
    _, ws_id, _, token = seeded
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/completeness",
        cookies={"access_token": token},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /gaps
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_gaps_returns_list(http, seeded):
    _, _, wi_id, token = seeded
    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/gaps",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_get_gaps_unauthenticated_returns_401(http, seeded):
    _, _, wi_id, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/gaps")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /next-step
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_next_step_returns_result(http, seeded):
    _, _, wi_id, token = seeded
    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/next-step",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "next_step" in data
    assert "message" in data
    assert "blocking" in data


@pytest.mark.asyncio
async def test_get_next_step_unauthenticated_returns_401(http, seeded):
    _, _, wi_id, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/next-step")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_next_step_nonexistent_returns_404(http, seeded):
    _, _, _, token = seeded
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/next-step",
        cookies={"access_token": token},
    )
    assert resp.status_code == 404
