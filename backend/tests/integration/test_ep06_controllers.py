"""Integration tests — EP-06 REST controllers.

Covers:
  POST   /api/v1/work-items/{id}/review-requests    — create (201)
  GET    /api/v1/work-items/{id}/review-requests    — list
  GET    /api/v1/review-requests/{id}               — single
  DELETE /api/v1/review-requests/{id}               — cancel (200)
  POST   /api/v1/review-requests/{id}/response      — respond (200)
  GET    /api/v1/review-requests/{id}/response      — get response
  GET    /api/v1/my/reviews                         — reviewer inbox
  GET    /api/v1/work-items/{id}/validations        — checklist
  POST   /api/v1/work-items/{id}/validations/{rule_id}/waive — waive
  GET    /api/v1/work-items/{id}/ready-gate         — gate check
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
            "email": "test@ep06.test",
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
        # Re-seed global validation rules that CASCADE wiped (workspace_id=NULL rows
        # get truncated when workspaces is truncated with CASCADE because
        # validation_requirements.workspace_id has a FK to workspaces).
        await conn.execute(
            text(
                """
                INSERT INTO validation_requirements (rule_id, label, required, applies_to, is_active)
                VALUES
                    ('spec_review_complete', 'Spec review complete', TRUE,  '', TRUE),
                    ('tech_review_complete', 'Tech review complete', FALSE, '', TRUE)
                ON CONFLICT (rule_id) DO NOTHING
                """
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
    """Seed: owner + reviewer users, workspace, work_item, work_item_version.

    Returns (owner_id, reviewer_id, workspace_id, work_item_id, version_id,
             owner_token, reviewer_token).
    """
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.models.workspace_membership import WorkspaceMembership
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_membership_repository_impl import (
        WorkspaceMembershipRepositoryImpl,
    )
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        uid = uuid4().hex[:6]

        owner = User.from_google_claims(
            sub=f"ep06-owner-{uid}", email=f"ep06-owner-{uid}@test.com", name="Owner", picture=None
        )
        await UserRepositoryImpl(session).upsert(owner)

        reviewer = User.from_google_claims(
            sub=f"ep06-rev-{uid}", email=f"ep06-rev-{uid}@test.com", name="Reviewer", picture=None
        )
        await UserRepositoryImpl(session).upsert(reviewer)

        ws = Workspace.create_from_email(email=owner.email, created_by=owner.id)
        ws.slug = f"ep06-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        for user in (owner, reviewer):
            await WorkspaceMembershipRepositoryImpl(session).create(
                WorkspaceMembership.create(
                    workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
                )
            )

        wi = WorkItem.create(
            title="EP-06 test item",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)

        # Create an initial version so review_requests.version_id FK is satisfiable.
        version = await WorkItemVersionRepositoryImpl(session).append(
            work_item_id=wi.id,
            snapshot={"title": wi.title},
            created_by=owner.id,
        )
        await session.commit()

    await engine.dispose()

    owner_token = _make_token(owner.id, ws.id)
    reviewer_token = _make_token(reviewer.id, ws.id)
    return owner.id, reviewer.id, ws.id, wi.id, version.id, owner_token, reviewer_token


# ---------------------------------------------------------------------------
# POST /api/v1/work-items/{id}/review-requests — 6.1 tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_review_request_201(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={
            "reviewer_id": str(reviewer_id),
            "version_id": str(version_id),
        },
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["work_item_id"] == str(wi_id)
    assert data["reviewer_id"] == str(reviewer_id)
    assert data["version_id"] == str(version_id)
    assert data["status"] == "pending"
    assert data["requested_by"] == str(owner_id)
    assert "id" in data


@pytest.mark.asyncio
async def test_create_review_request_self_review_forbidden(http, seeded):
    owner_id, _, _, wi_id, version_id, owner_token, _ = seeded

    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={
            "reviewer_id": str(owner_id),  # same as requester
            "version_id": str(version_id),
        },
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "SELF_REVIEW_FORBIDDEN"


@pytest.mark.asyncio
async def test_create_review_request_unauthenticated(http, seeded):
    _, reviewer_id, _, wi_id, version_id, _, _ = seeded
    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/work-items/{id}/review-requests + GET /review-requests/{id} — 6.2
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_review_requests(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    # Create one
    await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/review-requests",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert "responses" in data[0]


@pytest.mark.asyncio
async def test_get_single_review_request(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.get(
        f"/api/v1/review-requests/{request_id}",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["id"] == request_id


@pytest.mark.asyncio
async def test_get_review_request_not_found(http, seeded):
    _, _, _, _, _, owner_token, _ = seeded
    resp = await http.get(
        f"/api/v1/review-requests/{uuid4()}",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/review-requests/{id} — cancel (6.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_review_request_200(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.delete(
        f"/api/v1/review-requests/{request_id}",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_review_request_non_owner_403(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.delete(
        f"/api/v1/review-requests/{request_id}",
        cookies={"access_token": reviewer_token},  # reviewer is not the requester
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_cancel_already_cancelled_409(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    # Cancel first time
    await http.delete(
        f"/api/v1/review-requests/{request_id}",
        cookies={"access_token": owner_token},
    )

    # Cancel again → 409
    resp = await http.delete(
        f"/api/v1/review-requests/{request_id}",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "REVIEW_ALREADY_CLOSED"


# ---------------------------------------------------------------------------
# POST /api/v1/review-requests/{id}/response — respond (6.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_respond_approved_200(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "approved"},
        cookies={"access_token": reviewer_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["status"] == "closed"
    assert len(data["responses"]) == 1
    assert data["responses"][0]["decision"] == "approved"


@pytest.mark.asyncio
async def test_respond_rejected_requires_content(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    # rejected without content → 422
    resp = await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "rejected"},
        cookies={"access_token": reviewer_token},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "CONTENT_REQUIRED"


@pytest.mark.asyncio
async def test_respond_rejected_with_content_200(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "rejected", "content": "Needs more work"},
        cookies={"access_token": reviewer_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["responses"][0]["decision"] == "rejected"
    assert data["responses"][0]["content"] == "Needs more work"


@pytest.mark.asyncio
async def test_respond_non_assigned_reviewer_403(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    # Create third user as interloper
    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    # Owner tries to respond (not the reviewer)
    resp = await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "approved"},
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 403, resp.text
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_respond_already_closed_409(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    # First response
    await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "approved"},
        cookies={"access_token": reviewer_token},
    )

    # Second response → 409
    resp = await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "approved"},
        cookies={"access_token": reviewer_token},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "REVIEW_ALREADY_CLOSED"


# ---------------------------------------------------------------------------
# GET /api/v1/review-requests/{id}/response — 6.6
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_response_404_before_respond(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, _ = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    resp = await http.get(
        f"/api/v1/review-requests/{request_id}/response",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_response_200_after_respond(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    create_resp = await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )
    request_id = create_resp.json()["data"]["id"]

    await http.post(
        f"/api/v1/review-requests/{request_id}/response",
        json={"decision": "approved"},
        cookies={"access_token": reviewer_token},
    )

    resp = await http.get(
        f"/api/v1/review-requests/{request_id}/response",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["decision"] == "approved"


# ---------------------------------------------------------------------------
# GET /api/v1/my/reviews — reviewer inbox
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_my_reviews_empty(http, seeded):
    _, _, _, _, _, _, reviewer_token = seeded
    resp = await http.get("/api/v1/my/reviews", cookies={"access_token": reviewer_token})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_my_reviews_returns_pending(http, seeded):
    owner_id, reviewer_id, _, wi_id, version_id, owner_token, reviewer_token = seeded

    await http.post(
        f"/api/v1/work-items/{wi_id}/review-requests",
        json={"reviewer_id": str(reviewer_id), "version_id": str(version_id)},
        cookies={"access_token": owner_token},
    )

    resp = await http.get("/api/v1/my/reviews", cookies={"access_token": reviewer_token})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "pending"


# ---------------------------------------------------------------------------
# GET /api/v1/work-items/{id}/validations — checklist (6.8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_validations_checklist(http, seeded):
    _, _, _, wi_id, _, owner_token, _ = seeded

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/validations",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "required" in data
    assert "recommended" in data
    assert isinstance(data["required"], list)
    assert isinstance(data["recommended"], list)


@pytest.mark.asyncio
async def test_get_validations_unauthenticated(http, seeded):
    _, _, _, wi_id, _, _, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/validations")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/v1/work-items/{id}/validations/{rule_id}/waive — 6.9
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_waive_recommended_rule_200(http, seeded, migrated_database):
    """tech_review_complete is recommended (required=false) — waive should succeed."""
    _, _, _, wi_id, _, owner_token, _ = seeded

    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/validations/tech_review_complete/waive",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["rule_id"] == "tech_review_complete"
    assert data["status"] == "waived"
    assert data["waived_at"] is not None


@pytest.mark.asyncio
async def test_waive_required_rule_422(http, seeded):
    """spec_review_complete is required — waive must be rejected."""
    _, _, _, wi_id, _, owner_token, _ = seeded

    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/validations/spec_review_complete/waive",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "CANNOT_WAIVE_REQUIRED"


@pytest.mark.asyncio
async def test_waive_unknown_rule_404(http, seeded):
    _, _, _, wi_id, _, owner_token, _ = seeded

    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/validations/nonexistent_rule/waive",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/work-items/{id}/ready-gate — gate check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ready_gate_no_rules_passes(http, seeded):
    """With a fresh work item and no statuses, gate depends on seeded requirements.
    Since spec_review_complete is required and has no status → blocked."""
    _, _, _, wi_id, _, owner_token, _ = seeded

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/ready-gate",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "ok" in data
    assert "blockers" in data
    # spec_review_complete is required with no status → blocked
    assert data["ok"] is False
    assert any(b["rule_id"] == "spec_review_complete" for b in data["blockers"])


@pytest.mark.asyncio
async def test_ready_gate_after_waiving_recommended(http, seeded):
    """Waiving the recommended rule alone doesn't unblock — required still pending."""
    _, _, _, wi_id, _, owner_token, _ = seeded

    await http.post(
        f"/api/v1/work-items/{wi_id}/validations/tech_review_complete/waive",
        cookies={"access_token": owner_token},
    )

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/ready-gate",
        cookies={"access_token": owner_token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["ok"] is False
    # Only required blocker should remain
    assert all(b["rule_id"] != "tech_review_complete" for b in data["blockers"])


@pytest.mark.asyncio
async def test_ready_gate_unauthenticated(http, seeded):
    _, _, _, wi_id, _, _, _ = seeded
    resp = await http.get(f"/api/v1/work-items/{wi_id}/ready-gate")
    assert resp.status_code == 401
