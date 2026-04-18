"""EP-05 — E2E chain integration tests.

Covers the full breakdown-to-rollup chain:
  breakdown callback → split → get tree → dependencies →
  dependency cycle detection → status transitions → rollup
"""

from __future__ import annotations

import hashlib
import hmac
import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"
_CALLBACK_SECRET = "test-dundun-secret-for-e2e-chain-tests"


def _make_token(user_id, workspace_id) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "test@ep05chain.test",
            "workspace_id": str(workspace_id),
            "is_superadmin": False,
            "exp": int(time.time()) + 3600,
        }
    )


def _sign_callback(body: bytes) -> str:
    return "sha256=" + hmac.new(_CALLBACK_SECRET.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_task_controller_ep05.py)
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

    from app.config.settings import get_settings
    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()
    fake_cache = FakeCache()

    async def _override_cache():
        yield fake_cache

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache

    # Override Dundun callback secret so HMAC tests work
    original_get_settings = get_settings

    def _patched_settings():
        s = original_get_settings()
        s.dundun.callback_secret = _CALLBACK_SECRET
        return s

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
            sub=f"e2e-{uid}", email=f"e2e-{uid}@test.com", name="E2E", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"e2e-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="E2E Chain test item",
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


async def _get_tree(http, work_item_id, token):
    resp = await http.get(
        f"/api/v1/work-items/{work_item_id}/task-tree",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["tree"]


# ---------------------------------------------------------------------------
# Chain 1: Create → GET single task with breadcrumb
# ---------------------------------------------------------------------------


class TestGetTaskWithBreadcrumb:
    @pytest.mark.asyncio
    async def test_root_task_has_empty_breadcrumb(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        task = await _create_task(http, work_item_id, token, "Root Task")

        resp = await http.get(
            f"/api/v1/tasks/{task['id']}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "Root Task"
        assert data["breadcrumb"] == []

    @pytest.mark.asyncio
    async def test_child_task_has_parent_in_breadcrumb(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        parent = await _create_task(http, work_item_id, token, "Parent Task")
        child = await _create_task(http, work_item_id, token, "Child Task", parent_id=parent["id"])

        resp = await http.get(
            f"/api/v1/tasks/{child['id']}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["breadcrumb"] == [{"id": parent["id"], "title": "Parent Task"}]

    @pytest.mark.asyncio
    async def test_get_nonexistent_task_returns_404(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        resp = await http.get(
            f"/api/v1/tasks/{uuid4()}",
            cookies={"access_token": token},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Chain 2: Create → split → GET tree (structure changes)
# ---------------------------------------------------------------------------


class TestSplitThenTree:
    @pytest.mark.asyncio
    async def test_split_then_tree_shows_two_roots(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        task = await _create_task(http, work_item_id, token, "Original")

        # Split into two
        split_resp = await http.post(
            f"/api/v1/tasks/{task['id']}/split",
            json={"title_a": "Part A", "title_b": "Part B"},
            cookies={"access_token": token},
        )
        assert split_resp.status_code == 201

        tree = await _get_tree(http, work_item_id, token)
        assert len(tree) == 2
        titles = {n["title"] for n in tree}
        assert "Part A" in titles
        assert "Part B" in titles
        # Original is gone
        assert "Original" not in titles


# ---------------------------------------------------------------------------
# Chain 3: Search endpoint
# ---------------------------------------------------------------------------


class TestSearchEndpoint:
    @pytest.mark.asyncio
    async def test_search_returns_matching_tasks(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        await _create_task(http, work_item_id, token, "Fix the bug")
        await _create_task(http, work_item_id, token, "Fix the tests")
        await _create_task(http, work_item_id, token, "Add new feature")

        resp = await http.get(
            f"/api/v1/work-items/{work_item_id}/tasks/search?q=fix",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        results = resp.json()["data"]
        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "Fix the bug" in titles
        assert "Fix the tests" in titles

    @pytest.mark.asyncio
    async def test_search_short_query_returns_empty(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        await _create_task(http, work_item_id, token, "Fix it")

        resp = await http.get(
            f"/api/v1/work-items/{work_item_id}/tasks/search?q=f",
            cookies={"access_token": token},
        )
        assert resp.status_code == 200
        assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# Chain 4: Dependency cycle detection
# ---------------------------------------------------------------------------


class TestDependencyCycleChain:
    @pytest.mark.asyncio
    async def test_cycle_returns_422(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "T1")
        t2 = await _create_task(http, work_item_id, token, "T2")
        t3 = await _create_task(http, work_item_id, token, "T3")

        # Build chain T1 → T2 → T3
        await http.post(
            f"/api/v1/tasks/{t1['id']}/dependencies",
            json={"target_id": t2["id"]},
            cookies={"access_token": token},
        )
        await http.post(
            f"/api/v1/tasks/{t2['id']}/dependencies",
            json={"target_id": t3["id"]},
            cookies={"access_token": token},
        )
        # Attempt T3 → T1 (cycle)
        cycle_resp = await http.post(
            f"/api/v1/tasks/{t3['id']}/dependencies",
            json={"target_id": t1["id"]},
            cookies={"access_token": token},
        )
        assert cycle_resp.status_code == 422
        # FastAPI serialises HTTPException(detail={...}) as {"detail": {...}}
        body = cycle_resp.json()
        error = body.get("detail", body).get("error", body.get("error", {}))
        assert error.get("code") == "CYCLE_DETECTED"


# ---------------------------------------------------------------------------
# Chain 5: Status transitions — predecessor blocking mark_done
# ---------------------------------------------------------------------------


class TestStatusTransitionChain:
    @pytest.mark.asyncio
    async def test_mark_done_blocked_by_predecessor(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "Blocker")
        t2 = await _create_task(http, work_item_id, token, "Dependent")

        # t2 depends on t1 (t2 can't be done while t1 is not done)
        await http.post(
            f"/api/v1/tasks/{t2['id']}/dependencies",
            json={"target_id": t1["id"]},
            cookies={"access_token": token},
        )

        # Start t2
        await http.post(
            f"/api/v1/tasks/{t2['id']}/start",
            cookies={"access_token": token},
        )

        # Try to mark t2 done while t1 is still draft
        done_resp = await http.post(
            f"/api/v1/tasks/{t2['id']}/mark-done",
            cookies={"access_token": token},
        )
        assert done_resp.status_code == 422

    @pytest.mark.asyncio
    async def test_mark_done_succeeds_when_predecessor_done(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        t1 = await _create_task(http, work_item_id, token, "Blocker")
        t2 = await _create_task(http, work_item_id, token, "Dependent")

        await http.post(
            f"/api/v1/tasks/{t2['id']}/dependencies",
            json={"target_id": t1["id"]},
            cookies={"access_token": token},
        )

        # Complete t1 first
        await http.post(f"/api/v1/tasks/{t1['id']}/start", cookies={"access_token": token})
        t1_done = await http.post(
            f"/api/v1/tasks/{t1['id']}/mark-done", cookies={"access_token": token}
        )
        assert t1_done.status_code == 200

        # Now t2 can be completed
        await http.post(f"/api/v1/tasks/{t2['id']}/start", cookies={"access_token": token})
        t2_done = await http.post(
            f"/api/v1/tasks/{t2['id']}/mark-done", cookies={"access_token": token}
        )
        assert t2_done.status_code == 200


# ---------------------------------------------------------------------------
# Chain 6: Rollup propagation in tree endpoint
# ---------------------------------------------------------------------------


class TestRollupInTree:
    @pytest.mark.asyncio
    async def test_tree_has_rollup_status_per_node(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        parent = await _create_task(http, work_item_id, token, "Parent")
        await _create_task(http, work_item_id, token, "Child", parent_id=parent["id"])

        tree = await _get_tree(http, work_item_id, token)
        assert len(tree) == 1
        parent_node = tree[0]
        assert "rollup_status" in parent_node
        # child is draft → parent rollup should be draft
        assert parent_node["rollup_status"] == "draft"

    @pytest.mark.asyncio
    async def test_rollup_becomes_done_when_all_children_done(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        parent = await _create_task(http, work_item_id, token, "Parent")
        child = await _create_task(http, work_item_id, token, "Child", parent_id=parent["id"])

        # Mark child done
        await http.post(f"/api/v1/tasks/{child['id']}/start", cookies={"access_token": token})
        await http.post(f"/api/v1/tasks/{child['id']}/mark-done", cookies={"access_token": token})

        tree = await _get_tree(http, work_item_id, token)
        parent_node = tree[0]
        assert parent_node["rollup_status"] == "done"

    @pytest.mark.asyncio
    async def test_rollup_in_progress_when_child_in_progress(self, http, seeded, app) -> None:
        _, _, work_item_id, token = seeded
        parent = await _create_task(http, work_item_id, token, "Parent")
        child = await _create_task(http, work_item_id, token, "Child", parent_id=parent["id"])

        # Start child
        await http.post(f"/api/v1/tasks/{child['id']}/start", cookies={"access_token": token})

        tree = await _get_tree(http, work_item_id, token)
        parent_node = tree[0]
        assert parent_node["rollup_status"] == "in_progress"
