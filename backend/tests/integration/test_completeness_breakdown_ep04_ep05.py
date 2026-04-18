"""EP-04 + EP-05 cross-EP integration test.

Creates a work item (INITIATIVE type — breakdown is applicable),
adds 3 tasks via the task API, then asserts:
  1. GET /completeness returns breakdown dimension with score >= 0.8
  2. Creating a task invalidates the completeness cache (second fetch is not stale)
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
            "email": "test@ep0405.test",
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
    """Seed user + workspace + INITIATIVE work item."""
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
            sub=f"ep0405-{uid}", email=f"ep0405-{uid}@test.com", name="EP0405", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"ep0405-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title="EP0405 initiative",
            type=WorkItemType.INITIATIVE,  # breakdown is applicable for INITIATIVE
            owner_id=user.id,
            creator_id=user.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)
        await session.commit()
    await engine.dispose()

    token = _make_token(user.id, ws.id)
    return user.id, ws.id, wi.id, token


@pytest.mark.asyncio
async def test_breakdown_score_rises_with_tasks(http, seeded):
    """Adding 3 tasks to an INITIATIVE brings breakdown.score to 0.8."""
    _, _, wi_id, token = seeded
    cookies = {"access_token": token}

    # Baseline: 0 tasks → breakdown not filled, score 0.0
    resp = await http.get(f"/api/v1/work-items/{wi_id}/completeness", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]
    breakdown_before = next(d for d in data["dimensions"] if d["dimension"] == "breakdown")
    assert breakdown_before["score"] == pytest.approx(0.0)
    assert breakdown_before["filled"] is False

    # Add 3 tasks
    for i in range(3):
        resp = await http.post(
            f"/api/v1/work-items/{wi_id}/tasks",
            json={"title": f"Task {i + 1}", "display_order": i},
            cookies=cookies,
        )
        assert resp.status_code == 201, resp.text

    # After 3 tasks → breakdown.score should be 0.8
    resp = await http.get(f"/api/v1/work-items/{wi_id}/completeness", cookies=cookies)
    assert resp.status_code == 200
    data = resp.json()["data"]
    breakdown_after = next(d for d in data["dimensions"] if d["dimension"] == "breakdown")
    assert breakdown_after["score"] == pytest.approx(0.8)
    assert breakdown_after["filled"] is True


@pytest.mark.asyncio
async def test_create_task_invalidates_completeness_cache(http, seeded, app):
    """Creating a task must delete the completeness cache key so the next fetch recomputes."""
    _, _, wi_id, token = seeded
    cookies = {"access_token": token}

    # Prime the cache
    await http.get(f"/api/v1/work-items/{wi_id}/completeness", cookies=cookies)
    fake_cache = app._fake_cache
    cache_key = f"completeness:{wi_id}"
    assert await fake_cache.get(cache_key) is not None  # cache was populated

    # Create a task — should invalidate the cache
    resp = await http.post(
        f"/api/v1/work-items/{wi_id}/tasks",
        json={"title": "Task", "display_order": 0},
        cookies=cookies,
    )
    assert resp.status_code == 201

    # Cache should be gone
    assert await fake_cache.get(cache_key) is None
