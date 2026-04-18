"""EP-17 — Integration test for list work-items with lock summary embedding.

Scenario:
  GET /projects/{project_id}/work-items should embed lock_summary per item
    1. 3 items: 2 with locks, 1 without → correct lock_summary per item
    2. Single DB query for all locks (no N+1)
    3. held_by_me reflects caller_id
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_LIST_WORK_ITEMS_URL = "/api/v1/projects/{project_id}/work-items"
_ACQUIRE_LOCK_URL = "/api/v1/sections/{section_id}/lock"
_CSRF_TOKEN = "test-csrf-token-for-ep17-list-lock-summary"


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
                "oauth_states, workspaces, users, audit_events "
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
    """Seed 3 users + workspace + project + 3 work_items + sections. Returns dict of useful IDs."""
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
        # 3 users
        user1 = User.from_google_claims(
            sub="list-lock-user1-sub", email="user1@test.com", name="User 1", picture=None
        )
        await UserRepositoryImpl(session).upsert(user1)

        user2 = User.from_google_claims(
            sub="list-lock-user2-sub", email="user2@test.com", name="User 2", picture=None
        )
        await UserRepositoryImpl(session).upsert(user2)

        user3 = User.from_google_claims(
            sub="list-lock-user3-sub", email="user3@test.com", name="User 3", picture=None
        )
        await UserRepositoryImpl(session).upsert(user3)

        ws = Workspace.create_from_email(email="user1@test.com", created_by=user1.id)
        ws.slug = "list-lock-test"
        await WorkspaceRepositoryImpl(session).create(ws)

        for uid in (user1.id, user2.id, user3.id):
            await WorkspaceMembershipRepositoryImpl(session).create(
                WorkspaceMembership.create(
                    workspace_id=ws.id, user_id=uid, role="member", is_default=True
                )
            )

        # 3 work items
        wi1 = WorkItem.create(
            title="Item 1 (locked by user1)",
            type=WorkItemType.TASK,
            owner_id=user1.id,
            creator_id=user1.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi1, ws.id)

        wi2 = WorkItem.create(
            title="Item 2 (locked by user2)",
            type=WorkItemType.TASK,
            owner_id=user2.id,
            creator_id=user2.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi2, ws.id)

        wi3 = WorkItem.create(
            title="Item 3 (no lock)",
            type=WorkItemType.TASK,
            owner_id=user3.id,
            creator_id=user3.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi3, ws.id)

        # Create sections for each item
        for wi in (wi1, wi2, wi3):
            section = Section.create(
                work_item_id=wi.id,
                section_type=SectionType.SUMMARY,
                display_order=1,
                is_required=True,
                created_by=wi.creator_id,
            )
            await SectionRepositoryImpl(session).save(section)

        await session.commit()

    await engine.dispose()

    return {
        "user1_id": user1.id,
        "user2_id": user2.id,
        "user3_id": user3.id,
        "workspace_id": ws.id,
        "project_id": ws.id,  # project_id = workspace_id in this setup
        "wi1_id": wi1.id,
        "wi2_id": wi2.id,
        "wi3_id": wi3.id,
        "user1_token": _make_token(user1.id, ws.id),
        "user2_token": _make_token(user2.id, ws.id),
        "user3_token": _make_token(user3.id, ws.id),
    }


def _auth_headers(token: str) -> dict:
    """Build headers that satisfy both auth (cookie) and CSRF (double-submit)."""
    cookie_header = f"access_token={token}; csrf_token={_CSRF_TOKEN}"
    return {
        "Cookie": cookie_header,
        "X-CSRF-Token": _CSRF_TOKEN,
    }


async def _acquire_lock_for_section(
    http: AsyncClient, section_id, user_id, token: str
) -> None:
    """Helper to acquire a lock on a section."""
    from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl
    from sqlalchemy.ext.asyncio import create_async_engine as _create_engine, async_sessionmaker

    url = _ACQUIRE_LOCK_URL.format(section_id=section_id)
    resp = await http.post(url, headers=_auth_headers(token))
    assert resp.status_code == 201, f"Failed to acquire lock: {resp.text}"


# ---------------------------------------------------------------------------
# Test: list work-items with lock_summary embedding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_work_items_includes_lock_summary_per_item(http, seeded, migrated_database):
    """RED: GET /projects/{id}/work-items embeds lock_summary with has_locks, count, held_by_me"""
    # Get sections for wi1 and wi2 to acquire locks
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from sqlalchemy import select
        from app.infrastructure.persistence.models.orm import WorkItemSectionORM

        # Get sections for wi1 and wi2
        result = await session.execute(
            select(WorkItemSectionORM).where(
                WorkItemSectionORM.work_item_id.in_([seeded["wi1_id"], seeded["wi2_id"]])
            )
        )
        sections = result.scalars().all()
        wi1_section = next(s for s in sections if s.work_item_id == seeded["wi1_id"])
        wi2_section = next(s for s in sections if s.work_item_id == seeded["wi2_id"])

    await engine.dispose()

    # User1 acquires lock on wi1's section
    await _acquire_lock_for_section(http, wi1_section.id, seeded["user1_id"], seeded["user1_token"])

    # User2 acquires lock on wi2's section
    await _acquire_lock_for_section(http, wi2_section.id, seeded["user2_id"], seeded["user2_token"])

    # User3 lists items
    resp = await http.get(
        _LIST_WORK_ITEMS_URL.format(project_id=seeded["project_id"]),
        headers=_auth_headers(seeded["user3_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data["data"]["items"]

    # Find each item in response
    wi1_resp = next(i for i in items if i["id"] == str(seeded["wi1_id"]))
    wi2_resp = next(i for i in items if i["id"] == str(seeded["wi2_id"]))
    wi3_resp = next(i for i in items if i["id"] == str(seeded["wi3_id"]))

    # Verify wi1 has lock_summary with has_locks=true, count=1, held_by_me=false (user3 doesn't hold it)
    assert wi1_resp["lock_summary"] is not None
    assert wi1_resp["lock_summary"]["has_locks"] is True
    assert wi1_resp["lock_summary"]["count"] == 1
    assert wi1_resp["lock_summary"]["held_by_me"] is False

    # Verify wi2 has lock_summary with has_locks=true, count=1, held_by_me=false
    assert wi2_resp["lock_summary"] is not None
    assert wi2_resp["lock_summary"]["has_locks"] is True
    assert wi2_resp["lock_summary"]["count"] == 1
    assert wi2_resp["lock_summary"]["held_by_me"] is False

    # Verify wi3 has lock_summary with has_locks=false
    assert wi3_resp["lock_summary"] is not None
    assert wi3_resp["lock_summary"]["has_locks"] is False


@pytest.mark.asyncio
async def test_list_work_items_held_by_me_reflects_caller(http, seeded, migrated_database):
    """RED: held_by_me=true when caller holds the lock"""
    # Get sections
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from sqlalchemy import select
        from app.infrastructure.persistence.models.orm import WorkItemSectionORM

        result = await session.execute(
            select(WorkItemSectionORM).where(
                WorkItemSectionORM.work_item_id == seeded["wi1_id"]
            )
        )
        wi1_section = result.scalar_one()

    await engine.dispose()

    # User1 acquires lock on wi1
    await _acquire_lock_for_section(http, wi1_section.id, seeded["user1_id"], seeded["user1_token"])

    # User1 lists items — should see held_by_me=true
    resp = await http.get(
        _LIST_WORK_ITEMS_URL.format(project_id=seeded["project_id"]),
        headers=_auth_headers(seeded["user1_token"]),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    items = data["data"]["items"]

    wi1_resp = next(i for i in items if i["id"] == str(seeded["wi1_id"]))
    assert wi1_resp["lock_summary"]["has_locks"] is True
    assert wi1_resp["lock_summary"]["held_by_me"] is True
