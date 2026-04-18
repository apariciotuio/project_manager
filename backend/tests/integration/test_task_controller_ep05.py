"""EP-05 — Integration tests for task hierarchy + dependency controller.

Tests split, merge, reorder, dependency add/remove/list, tree endpoint,
and blocked tasks endpoint.
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
            "email": "test@ep05.test",
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
                "TRUNCATE TABLE task_dependencies, task_node_section_links, task_nodes, "
                "work_item_section_versions, work_item_sections, "
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
            sub=f"ep05-{uid}", email=f"ep05-{uid}@test.com", name="EP05", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"ep05-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="EP-05 test item",
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_task(http, work_item_id, token, title="Task", parent_id=None):
    body = {"title": title, "display_order": 0}
    if parent_id:
        body["parent_id"] = str(parent_id)
    resp = await http.post(
        f"/api/v1/work-items/{work_item_id}/tasks",
        json=body,
        cookies={"access_token": token},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Tree
# ---------------------------------------------------------------------------


class TestGetTaskTree:
    @pytest.mark.asyncio
    async def test_empty_tree(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        resp = await http.get(
            f"/api/v1/work-items/{work_item_id}/task-tree",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["tree"] == []

    @pytest.mark.asyncio
    async def test_tree_with_node(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        await _create_task(http, work_item_id, token, "Root Task")

        resp = await http.get(
            f"/api/v1/work-items/{work_item_id}/task-tree",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        tree = resp.json()["data"]["tree"]
        assert len(tree) == 1
        assert tree[0]["title"] == "Root Task"


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------


class TestTaskSplit:
    @pytest.mark.asyncio
    async def test_split_returns_201_with_two_nodes(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        task = await _create_task(http, work_item_id, token, "To Split")

        resp = await http.post(
            f"/api/v1/tasks/{task['id']}/split",
            json={"title_a": "Part A", "title_b": "Part B"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert "a" in data
        assert "b" in data
        assert data["a"]["title"] == "Part A"
        assert data["b"]["title"] == "Part B"

    @pytest.mark.asyncio
    async def test_split_not_found_returns_404(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        resp = await http.post(
            f"/api/v1/tasks/{uuid4()}/split",
            json={"title_a": "A", "title_b": "B"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_split_empty_title_returns_422(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        task = await _create_task(http, work_item_id, token, "To Split")

        resp = await http.post(
            f"/api/v1/tasks/{task['id']}/split",
            json={"title_a": "", "title_b": "B"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


class TestTaskMerge:
    @pytest.mark.asyncio
    async def test_merge_returns_201(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")

        resp = await http.post(
            f"/api/v1/work-items/{work_item_id}/tasks/merge",
            json={"source_ids": [t1["id"], t2["id"]], "title": "Merged"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()["data"]
        assert data["title"] == "Merged"

    @pytest.mark.asyncio
    async def test_merge_single_source_returns_422(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")

        resp = await http.post(
            f"/api/v1/work-items/{work_item_id}/tasks/merge",
            json={"source_ids": [t1["id"]], "title": "M"},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Reorder
# ---------------------------------------------------------------------------


class TestTaskReorder:
    @pytest.mark.asyncio
    async def test_reorder_returns_200(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")
        t3 = await _create_task(http, work_item_id, token, "T3")

        resp = await http.patch(
            f"/api/v1/work-items/{work_item_id}/tasks/reorder",
            json={"ordered_ids": [t3["id"], t1["id"], t2["id"]]},
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_reorder_unknown_id_returns_422(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")

        resp = await http.patch(
            f"/api/v1/work-items/{work_item_id}/tasks/reorder",
            json={"ordered_ids": [t1["id"], str(uuid4())]},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


class TestDependencyEndpoints:
    @pytest.mark.asyncio
    async def test_add_dependency_returns_201(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")

        resp = await http.post(
            f"/api/v1/tasks/{t1['id']}/dependencies",
            json={"target_id": t2["id"]},
            cookies={"access_token": token},
        )
        assert resp.status_code == 201, resp.text

    @pytest.mark.asyncio
    async def test_add_cycle_returns_422(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")

        await http.post(
            f"/api/v1/tasks/{t1['id']}/dependencies",
            json={"target_id": t2["id"]},
            cookies={"access_token": token},
        )
        resp = await http.post(
            f"/api/v1/tasks/{t2['id']}/dependencies",
            json={"target_id": t1["id"]},
            cookies={"access_token": token},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_delete_dependency_returns_204(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")

        add_resp = await http.post(
            f"/api/v1/tasks/{t1['id']}/dependencies",
            json={"target_id": t2["id"]},
            cookies={"access_token": token},
        )
        dep_id = add_resp.json()["data"]["id"]

        del_resp = await http.delete(
            f"/api/v1/dependencies/{dep_id}",
            cookies={"access_token": token},
        )
        assert del_resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        resp = await http.delete(
            f"/api/v1/dependencies/{uuid4()}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_blocked_tasks_returns_200(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        resp = await http.get(
            f"/api/v1/work-items/{work_item_id}/tasks/blocked",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []
