"""MF-2 regression tests — workspace_id guards on task_controller + suggestion_controller.

A JWT without workspace_id must be rejected with 401 + NO_WORKSPACE on every
endpoint that routes through get_current_user.
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.adapters.jwt_adapter import JwtAdapter

_JWT_SECRET = "change-me-in-prod-use-32-chars-or-more-please"


def _token_no_workspace(user_id) -> str:
    jwt = JwtAdapter(secret=_JWT_SECRET, issuer="wmp", audience="wmp-web")
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": "noworkspace@test.com",
            # workspace_id intentionally omitted
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
                "TRUNCATE TABLE task_dependencies, task_node_section_links, task_nodes, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import get_cache_adapter, get_dundun_client
    from tests.fakes.fake_dundun_client import FakeDundunClient
    from tests.fakes.fake_repositories import FakeCache

    fastapi_app = _create_app()
    fake_cache = FakeCache()
    fake_dundun = FakeDundunClient()

    async def _override_cache():
        yield fake_cache

    def _override_dundun():
        return fake_dundun

    fastapi_app.dependency_overrides[get_cache_adapter] = _override_cache
    fastapi_app.dependency_overrides[get_dundun_client] = _override_dundun

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
def no_ws_token():
    return _token_no_workspace(uuid4())


def _expect_no_workspace(resp) -> None:
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["error"]["code"] == "NO_WORKSPACE"


# ---------------------------------------------------------------------------
# task_controller endpoints — no workspace token → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_tree_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/task-tree",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_get_task_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/tasks/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_create_task_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/work-items/{uuid4()}/tasks",
        json={"title": "Test task"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_update_task_no_workspace(http, no_ws_token):
    resp = await http.patch(
        f"/api/v1/tasks/{uuid4()}",
        json={"title": "Updated"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_delete_task_no_workspace(http, no_ws_token):
    resp = await http.delete(
        f"/api/v1/tasks/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_start_task_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/tasks/{uuid4()}/start",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_mark_done_task_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/tasks/{uuid4()}/mark-done",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_reopen_task_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/tasks/{uuid4()}/reopen",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_split_task_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/tasks/{uuid4()}/split",
        json={"title_a": "A", "title_b": "B"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_merge_tasks_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/work-items/{uuid4()}/tasks/merge",
        json={"source_ids": [str(uuid4())], "title": "Merged"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_reorder_tasks_no_workspace(http, no_ws_token):
    resp = await http.patch(
        f"/api/v1/work-items/{uuid4()}/tasks/reorder",
        json={"ordered_ids": [str(uuid4())]},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_get_blocked_tasks_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/tasks/blocked",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_add_dependency_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/tasks/{uuid4()}/dependencies",
        json={"target_id": str(uuid4())},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_remove_dependency_no_workspace(http, no_ws_token):
    resp = await http.delete(
        f"/api/v1/dependencies/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_search_tasks_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/tasks/search?q=test",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


# ---------------------------------------------------------------------------
# suggestion_controller endpoints — no workspace token → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_suggestions_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/work-items/{uuid4()}/suggestion-sets",
        json={"thread_id": None},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_list_suggestion_sets_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/work-items/{uuid4()}/suggestion-sets",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_get_suggestion_batch_no_workspace(http, no_ws_token):
    resp = await http.get(
        f"/api/v1/suggestion-sets/{uuid4()}",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_patch_suggestion_item_no_workspace(http, no_ws_token):
    resp = await http.patch(
        f"/api/v1/suggestion-items/{uuid4()}",
        json={"status": "accepted"},
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)


@pytest.mark.asyncio
async def test_apply_suggestion_batch_no_workspace(http, no_ws_token):
    resp = await http.post(
        f"/api/v1/suggestion-sets/{uuid4()}/apply",
        cookies={"access_token": no_ws_token},
    )
    _expect_no_workspace(resp)
