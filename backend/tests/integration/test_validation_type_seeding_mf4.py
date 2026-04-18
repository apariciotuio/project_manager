"""MF-4 regression — validation seeding uses real work_item.type.

Scenarios:
- work item with type 'bug' + type-specific rule for 'bug' + global rule
  → GET /validations returns BOTH (type match + global)
- work item with type 'task' + type-specific rule for 'bug' only
  → GET /validations returns only the global rule (no 'bug' rules)
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
            "email": "test@mf4.test",
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
                "TRUNCATE TABLE review_responses, review_requests, "
                "validation_status, validation_requirements, "
                "work_item_section_versions, work_item_sections, "
                "work_item_validators, work_item_versions, "
                "gap_findings, assistant_suggestions, conversation_threads, "
                "ownership_history, state_transitions, work_item_drafts, "
                "work_items, templates, workspace_memberships, sessions, "
                "oauth_states, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
        # Seed: one global rule (applies_to='') + one bug-specific rule (applies_to='bug')
        await conn.execute(
            text(
                """
                INSERT INTO validation_requirements (rule_id, label, required, applies_to, is_active)
                VALUES
                    ('global_rule', 'Global Rule', TRUE, '', TRUE),
                    ('bug_only_rule', 'Bug Only Rule', FALSE, 'bug', TRUE)
                """
            )
        )
    await engine.dispose()

    from app.main import create_app as _create_app
    from app.presentation.dependencies import _cached_jwt_adapter, get_cache_adapter
    from tests.fakes.fake_repositories import FakeCache

    # Clear the lru_cache so the JWT adapter is rebuilt with the current test settings,
    # not a stale instance from a prior test module that ran earlier in the suite.
    _cached_jwt_adapter.cache_clear()

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


async def _seed_work_item(migrated_database, work_item_type: str):
    """Seed user + workspace + work item with given type. Returns (user_id, ws_id, wi_id, token)."""
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
    uid = uuid4().hex[:6]
    async with factory() as session:
        user = User.from_google_claims(
            sub=f"mf4-{uid}", email=f"mf4-{uid}@test.com", name="MF4", picture=None
        )
        await UserRepositoryImpl(session).upsert(user)

        ws = Workspace.create_from_email(email=user.email, created_by=user.id)
        ws.slug = f"mf4-{uid}"
        await WorkspaceRepositoryImpl(session).create(ws)
        await WorkspaceMembershipRepositoryImpl(session).create(
            WorkspaceMembership.create(
                workspace_id=ws.id, user_id=user.id, role="admin", is_default=True
            )
        )

        wi = WorkItem.create(
            title=f"MF-4 {work_item_type} item",
            type=WorkItemType(work_item_type),
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
async def test_validations_bug_type_returns_global_and_type_specific(http, migrated_database):
    """Bug work item → global_rule + bug_only_rule both returned."""
    _, _, wi_id, token = await _seed_work_item(migrated_database, "bug")

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/validations",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    all_rule_ids = {r["rule_id"] for r in data["required"] + data["recommended"]}
    assert "global_rule" in all_rule_ids, "global rule must always appear"
    assert "bug_only_rule" in all_rule_ids, "bug-specific rule must appear for bug work items"


@pytest.mark.asyncio
async def test_validations_task_type_returns_only_global(http, migrated_database):
    """Task work item → only global_rule, not bug_only_rule."""
    _, _, wi_id, token = await _seed_work_item(migrated_database, "task")

    resp = await http.get(
        f"/api/v1/work-items/{wi_id}/validations",
        cookies={"access_token": token},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    all_rule_ids = {r["rule_id"] for r in data["required"] + data["recommended"]}
    assert "global_rule" in all_rule_ids, "global rule must always appear"
    assert "bug_only_rule" not in all_rule_ids, (
        "bug-specific rule must NOT appear for task work items"
    )
