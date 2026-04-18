"""EP-01 Phase 4 — Work Item controller integration tests.

Uses real FastAPI app + real Postgres testcontainer.
Auth via JWT cookies minted with the test secret.
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
async def http(app) -> AsyncClient:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        yield client


async def _seed(migrated_database) -> tuple[User, Workspace, str]:
    """Seed one user + workspace + admin membership. Returns (user, workspace, jwt_cookie_value)."""
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        workspaces = WorkspaceRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-wi-test", email="wi@test.com", name="WI", picture=None
        )
        await users.upsert(user)
        ws = Workspace.create_from_email(email="wi@test.com", created_by=user.id)
        ws.slug = "wi-test"
        await workspaces.create(ws)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )
        await session.commit()

    await engine.dispose()

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
    return user, ws, token


async def _seed_second_user(migrated_database, workspace_id: UUID) -> tuple[User, str]:
    """Seed a second user in the same workspace. Returns (user, jwt_cookie_value)."""
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-wi-other", email="other@test.com", name="Other", picture=None
        )
        await users.upsert(user)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=workspace_id, user_id=user.id, role="member", is_default=True
            )
        )
        await session.commit()

    await engine.dispose()

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, token


async def _seed_suspended_user(migrated_database, workspace_id: UUID) -> tuple[User, str]:
    """Seed a suspended user in the same workspace."""
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        users = UserRepositoryImpl(session)
        memberships = WorkspaceMembershipRepositoryImpl(session)

        user = User.from_google_claims(
            sub="sub-wi-suspended", email="suspended@test.com", name="Sus", picture=None
        )
        # Directly suspend after creation
        user.status = "suspended"  # type: ignore[assignment]
        await users.upsert(user)
        await memberships.create(
            WorkspaceMembership.create(
                workspace_id=workspace_id, user_id=user.id, role="member", is_default=False
            )
        )
        await session.commit()

    await engine.dispose()

    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )
    return user, token


def _auth(token: str) -> dict:
    return {"access_token": token}


async def _create_item(http: AsyncClient, token: str, project_id: UUID, **kwargs) -> dict:
    payload = {"title": "Test Item", "type": "task", "project_id": str(project_id), **kwargs}
    r = await http.post("/api/v1/work-items", json=payload, cookies=_auth(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_work_item_returns_201(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()

    r = await http.post(
        "/api/v1/work-items",
        json={"title": "New Task", "type": "task", "project_id": str(project_id)},
        cookies=_auth(token),
    )

    assert r.status_code == 201
    data = r.json()["data"]
    assert data["title"] == "New Task"
    assert data["state"] == "draft"
    assert data["type"] == "task"
    assert isinstance(data["completeness_score"], int)
    assert data["next_step"] == "add_description_and_transition_to_in_clarification"
    assert data["override_info"] is None


@pytest.mark.asyncio
async def test_create_work_item_response_shape(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()

    item = await _create_item(http, token, project_id, title="Shape Test", type="bug")
    assert "id" in item
    assert "workspace_id" in item
    assert "project_id" in item
    assert "derived_state" in item
    assert "created_at" in item


@pytest.mark.asyncio
async def test_get_work_item_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.get(f"/api/v1/work-items/{item['id']}", cookies=_auth(token))
    assert r.status_code == 200
    assert r.json()["data"]["id"] == item["id"]


@pytest.mark.asyncio
async def test_patch_non_state_fields_returns_200(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.patch(
        f"/api/v1/work-items/{item['id']}",
        json={"title": "Updated Title", "description": "Some description"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "Updated Title"
    assert r.json()["data"]["description"] == "Some description"


@pytest.mark.asyncio
async def test_transition_valid_returns_200_and_persists_row(
    http, migrated_database, db_session
) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/transitions",
        json={"target_state": "in_clarification", "reason": "starting"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["data"]["state"] == "in_clarification"

    # Check DB row
    await db_session.execute(
        text("SELECT set_config('app.current_workspace', :wid, true)"), {"wid": str(ws.id)}
    )
    rows = await db_session.execute(
        text(
            "SELECT from_state, to_state FROM state_transitions WHERE work_item_id = :id ORDER BY triggered_at DESC"
        ),
        {"id": item["id"]},
    )
    transitions = rows.fetchall()
    assert any(t.to_state == "in_clarification" for t in transitions)


@pytest.mark.asyncio
async def test_force_ready_valid_sets_has_override(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/force-ready",
        json={
            "justification": "This is a valid justification longer than ten chars",
            "confirmed": True,
        },
        cookies=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["has_override"] is True
    assert data["state"] == "ready"
    assert data["override_info"] is not None
    assert data["override_info"]["justified"] is True


@pytest.mark.asyncio
async def test_reassign_owner_valid_returns_200(http, migrated_database, db_session) -> None:
    user, ws, token = await _seed(migrated_database)
    other_user, other_token = await _seed_second_user(migrated_database, ws.id)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.patch(
        f"/api/v1/work-items/{item['id']}/owner",
        json={"new_owner_id": str(other_user.id), "reason": "delegation"},
        cookies=_auth(token),
    )
    assert r.status_code == 200
    assert r.json()["data"]["owner_id"] == str(other_user.id)

    # Check ownership_history row persisted
    await db_session.execute(
        text("SELECT set_config('app.current_workspace', :wid, true)"), {"wid": str(ws.id)}
    )
    rows = await db_session.execute(
        text("SELECT new_owner_id FROM ownership_history WHERE work_item_id = :id"),
        {"id": item["id"]},
    )
    records = rows.fetchall()
    assert any(str(r.new_owner_id) == str(other_user.id) for r in records)


@pytest.mark.asyncio
async def test_get_transitions_ordered_desc(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    await http.post(
        f"/api/v1/work-items/{item['id']}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_auth(token),
    )
    await http.post(
        f"/api/v1/work-items/{item['id']}/transitions",
        json={"target_state": "in_review"},
        cookies=_auth(token),
    )

    r = await http.get(f"/api/v1/work-items/{item['id']}/transitions", cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 2
    # Most recent should be in_review
    assert data[0]["to_state"] == "in_review"


@pytest.mark.asyncio
async def test_get_ownership_history_ordered_desc(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    other_user, _ = await _seed_second_user(migrated_database, ws.id)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    await http.patch(
        f"/api/v1/work-items/{item['id']}/owner",
        json={"new_owner_id": str(other_user.id)},
        cookies=_auth(token),
    )

    r = await http.get(f"/api/v1/work-items/{item['id']}/ownership-history", cookies=_auth(token))
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) >= 1
    assert str(data[0]["new_owner_id"]) == str(other_user.id)


@pytest.mark.asyncio
async def test_list_with_state_filter_returns_matching(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()

    await _create_item(http, token, project_id, title="Item Draft")
    item2 = await _create_item(http, token, project_id, title="Item to Clarify")

    # Transition item2 to in_clarification
    await http.post(
        f"/api/v1/work-items/{item2['id']}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_auth(token),
    )

    r = await http.get(
        f"/api/v1/projects/{project_id}/work-items?state=in_clarification",
        cookies=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(i["state"] == "in_clarification" for i in data["items"])
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_with_has_override_filter(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()

    await _create_item(http, token, project_id, title="Normal")
    item2 = await _create_item(http, token, project_id, title="Override Item")

    await http.post(
        f"/api/v1/work-items/{item2['id']}/force-ready",
        json={"justification": "Force override justification here", "confirmed": True},
        cookies=_auth(token),
    )

    r = await http.get(
        f"/api/v1/projects/{project_id}/work-items?has_override=true",
        cookies=_auth(token),
    )
    assert r.status_code == 200
    data = r.json()["data"]
    assert all(i["has_override"] is True for i in data["items"])


@pytest.mark.asyncio
async def test_delete_draft_returns_204(http, migrated_database, db_session) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.delete(f"/api/v1/work-items/{item['id']}", cookies=_auth(token))
    assert r.status_code == 204

    # Verify soft-delete in DB
    await db_session.execute(
        text("SELECT set_config('app.current_workspace', :wid, true)"), {"wid": str(ws.id)}
    )
    row = await db_session.execute(
        text("SELECT deleted_at FROM work_items WHERE id = :id"),
        {"id": item["id"]},
    )
    record = row.fetchone()
    assert record is not None
    assert record.deleted_at is not None


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_missing_title_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)

    r = await http.post(
        "/api/v1/work-items",
        json={"type": "task", "project_id": str(uuid4())},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["field"] == "title"


@pytest.mark.asyncio
async def test_create_title_too_short_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)

    r = await http.post(
        "/api/v1/work-items",
        json={"title": "AB", "type": "task", "project_id": str(uuid4())},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_get_unknown_id_returns_404(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)

    r = await http.get(f"/api/v1/work-items/{uuid4()}", cookies=_auth(token))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "WORK_ITEM_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_item_in_other_workspace_returns_404(http, migrated_database) -> None:
    """Existence disclosure protection: cross-workspace access returns 404, not 403."""
    user, ws, token = await _seed(migrated_database)

    # Create item in ws1
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    # Build token for a different workspace
    other_ws_id = uuid4()
    jwt = JwtAdapter(
        secret="change-me-in-prod-use-32-chars-or-more-please",
        issuer="wmp",
        audience="wmp-web",
    )
    other_token = jwt.encode(
        {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(other_ws_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )

    r = await http.get(f"/api/v1/work-items/{item['id']}", cookies=_auth(other_token))
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_with_state_field_returns_422_use_transition(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.patch(
        f"/api/v1/work-items/{item['id']}",
        json={"state": "in_review"},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["reason"] == "use_transition_endpoint"


@pytest.mark.asyncio
async def test_transition_invalid_edge_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/transitions",
        json={"target_state": "exported"},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "INVALID_TRANSITION"
    assert error["details"]["from_state"] == "draft"
    assert error["details"]["to_state"] == "exported"


@pytest.mark.asyncio
async def test_force_ready_short_justification_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/force-ready",
        json={"justification": "short", "confirmed": True},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["field"] == "justification"


@pytest.mark.asyncio
async def test_force_ready_confirmed_false_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/force-ready",
        json={"justification": "This is long enough justification", "confirmed": False},
        cookies=_auth(token),
    )
    assert r.status_code == 422
    error = r.json()["error"]
    assert error["code"] == "CONFIRMATION_REQUIRED"
    assert "pending_validation_ids" in error["details"]


@pytest.mark.asyncio
async def test_force_ready_by_non_owner_returns_403(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    other_user, other_token = await _seed_second_user(migrated_database, ws.id)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    r = await http.post(
        f"/api/v1/work-items/{item['id']}/force-ready",
        json={
            "justification": "This justification is long enough to pass validation",
            "confirmed": True,
        },
        cookies=_auth(other_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "NOT_OWNER"


@pytest.mark.asyncio
async def test_reassign_by_non_owner_returns_403(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    other_user, other_token = await _seed_second_user(migrated_database, ws.id)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    # other_user tries to reassign
    r = await http.patch(
        f"/api/v1/work-items/{item['id']}/owner",
        json={"new_owner_id": str(other_user.id)},
        cookies=_auth(other_token),
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "NOT_OWNER"


@pytest.mark.asyncio
async def test_delete_non_draft_returns_422(http, migrated_database) -> None:
    user, ws, token = await _seed(migrated_database)
    project_id = uuid4()
    item = await _create_item(http, token, project_id)

    # Transition to in_clarification first
    await http.post(
        f"/api/v1/work-items/{item['id']}/transitions",
        json={"target_state": "in_clarification"},
        cookies=_auth(token),
    )

    r = await http.delete(f"/api/v1/work-items/{item['id']}", cookies=_auth(token))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "CANNOT_DELETE_NON_DRAFT"


@pytest.mark.asyncio
async def test_no_auth_cookie_returns_401(http, migrated_database) -> None:
    r = await http.post(
        "/api/v1/work-items",
        json={"title": "Test", "type": "task", "project_id": str(uuid4())},
    )
    assert r.status_code == 401
