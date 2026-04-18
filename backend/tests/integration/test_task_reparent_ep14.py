"""EP-14 — Integration tests: reparent + sibling reorder endpoints.

Tests exercise the full stack: controller → service → fake repo (no DB needed
since the fake wires in through create_app + seeded).

For the endpoint layer we use the same pattern as test_task_controller_ep05.py.
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
            "email": "test@ep14.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


# ---------------------------------------------------------------------------
# Fixtures (mirrored from ep05 integration test)
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
            sub=f"ep14-{uid}", email=f"ep14-{uid}@test.com", name="EP14", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"ep14-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="EP-14 reparent test",
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


async def _reparent(http, node_id, token, *, new_parent_id=None, position=None):
    body: dict = {}
    if new_parent_id is not None:
        body["new_parent_id"] = str(new_parent_id)
    if position is not None:
        body["position"] = position
    return await http.patch(
        f"/api/v1/tasks/{node_id}/parent",
        json=body,
        cookies={"access_token": token},
    )


# ---------------------------------------------------------------------------
# PATCH /tasks/{id}/parent
# ---------------------------------------------------------------------------


class TestReparentEndpoint:
    @pytest.mark.asyncio
    async def test_reparent_position_zero_becomes_first(self, http, seeded, app) -> None:
        """Reparent + position=0 → target becomes first sibling at new parent."""
        _, _, wi, token = seeded

        await _create_task(http, wi, token, "A")
        await _create_task(http, wi, token, "B")
        # 'moving' currently under a child parent
        parent_task = await _create_task(http, wi, token, "OldParent")
        moving = await _create_task(http, wi, token, "Moving", parent_id=parent_task["id"])

        resp = await _reparent(http, moving["id"], token, new_parent_id=None, position=0)

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["parent_id"] is None
        assert data["display_order"] == 0

    @pytest.mark.asyncio
    async def test_reparent_position_end_appends(self, http, seeded, app) -> None:
        """Reparent + position=N (end) → target appended after last sibling."""
        _, _, wi, token = seeded

        await _create_task(http, wi, token, "A")
        await _create_task(http, wi, token, "B")
        parent_task = await _create_task(http, wi, token, "OldParent")
        moving = await _create_task(http, wi, token, "Moving", parent_id=parent_task["id"])

        # 2 root siblings (a, b) + OldParent = 3 roots. Moving at position=3 → end
        resp = await _reparent(http, moving["id"], token, new_parent_id=None, position=3)

        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["parent_id"] is None
        assert data["display_order"] == 3

    @pytest.mark.asyncio
    async def test_reparent_position_out_of_range_returns_422(self, http, seeded, app) -> None:
        """position > sibling count → 422."""
        _, _, wi, token = seeded

        parent_task = await _create_task(http, wi, token, "OldParent")
        moving = await _create_task(http, wi, token, "Moving", parent_id=parent_task["id"])

        # Only 1 root sibling (OldParent). position=99 is way out of range.
        resp = await _reparent(http, moving["id"], token, new_parent_id=None, position=99)
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_cross_parent_reparent_old_siblings_renumber(self, http, seeded, app) -> None:
        """After moving a child out, remaining siblings under old parent are gapless."""
        _, _, wi, token = seeded

        old_parent = await _create_task(http, wi, token, "OldParent")
        await _create_task(http, wi, token, "X", parent_id=old_parent["id"])
        moving = await _create_task(http, wi, token, "Moving", parent_id=old_parent["id"])
        await _create_task(http, wi, token, "Y", parent_id=old_parent["id"])

        new_parent = await _create_task(http, wi, token, "NewParent")

        resp = await _reparent(
            http, moving["id"], token, new_parent_id=new_parent["id"], position=0
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["parent_id"] == new_parent["id"]
        assert data["display_order"] == 0

        # Verify old siblings via tree
        tree_resp = await http.get(
            f"/api/v1/work-items/{wi}/task-tree",
            cookies={"access_token": token},
        )
        assert tree_resp.status_code == 200
        tree = tree_resp.json()["data"]["tree"]

        # Find old_parent node and its children
        def find_node(tree, node_id):
            for n in tree:
                if n["id"] == node_id:
                    return n
                found = find_node(n.get("children", []), node_id)
                if found:
                    return found
            return None

        op_node = find_node(tree, old_parent["id"])
        assert op_node is not None
        children = op_node["children"]
        # Only x and y remain, gapless orders
        assert len(children) == 2
        orders = sorted(c["display_order"] for c in children)
        assert orders == [0, 1]

    @pytest.mark.asyncio
    async def test_same_parent_reorder_via_reparent(self, http, seeded, app) -> None:
        """new_parent_id == old_parent_id → pure reorder within same parent."""
        _, _, wi, token = seeded

        parent_task = await _create_task(http, wi, token, "Parent")
        await _create_task(http, wi, token, "A", parent_id=parent_task["id"])
        await _create_task(http, wi, token, "B", parent_id=parent_task["id"])
        c = await _create_task(http, wi, token, "C", parent_id=parent_task["id"])

        # Move c to position 0 (same parent)
        resp = await _reparent(http, c["id"], token, new_parent_id=parent_task["id"], position=0)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["display_order"] == 0


# ---------------------------------------------------------------------------
# POST /work-items/{id}/tasks/reorder-siblings
# ---------------------------------------------------------------------------


class TestReorderSiblingsEndpoint:
    @pytest.mark.asyncio
    async def test_reorder_siblings_happy_path(self, http, seeded, app) -> None:
        _, _, wi, token = seeded

        parent_task = await _create_task(http, wi, token, "Parent")
        a = await _create_task(http, wi, token, "A", parent_id=parent_task["id"])
        b = await _create_task(http, wi, token, "B", parent_id=parent_task["id"])
        c = await _create_task(http, wi, token, "C", parent_id=parent_task["id"])

        resp = await http.post(
            f"/api/v1/work-items/{wi}/tasks/reorder-siblings",
            json={
                "parent_id": parent_task["id"],
                "ordered_ids": [c["id"], a["id"], b["id"]],
            },
            cookies={"access_token": token},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["ordered_ids"] == [c["id"], a["id"], b["id"]]

    @pytest.mark.asyncio
    async def test_reorder_siblings_missing_id_returns_422(self, http, seeded, app) -> None:
        _, _, wi, token = seeded

        parent_task = await _create_task(http, wi, token, "Parent")
        a = await _create_task(http, wi, token, "A", parent_id=parent_task["id"])
        await _create_task(http, wi, token, "B", parent_id=parent_task["id"])

        resp = await http.post(
            f"/api/v1/work-items/{wi}/tasks/reorder-siblings",
            json={
                "parent_id": parent_task["id"],
                "ordered_ids": [a["id"]],  # missing b
            },
            cookies={"access_token": token},
        )
        assert resp.status_code == 422, resp.text

    @pytest.mark.asyncio
    async def test_reorder_siblings_foreign_id_returns_422(self, http, seeded, app) -> None:
        _, _, wi, token = seeded

        parent_task = await _create_task(http, wi, token, "Parent")
        a = await _create_task(http, wi, token, "A", parent_id=parent_task["id"])
        other = await _create_task(http, wi, token, "Other")  # root, not under parent

        resp = await http.post(
            f"/api/v1/work-items/{wi}/tasks/reorder-siblings",
            json={
                "parent_id": parent_task["id"],
                "ordered_ids": [a["id"], other["id"]],
            },
            cookies={"access_token": token},
        )
        assert resp.status_code == 422, resp.text
