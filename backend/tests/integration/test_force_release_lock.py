"""EP-17 — Integration test for force-release lock with reason param.

Scenario:
  POST /sections/{id}/lock/force-release
    1. force-release with reason → audit event includes reason in context
    2. force-release without reason → audit event has reason=None
"""
from __future__ import annotations

import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_FORCE_RELEASE_URL = "/api/v1/sections/{sid}/lock/force-release"
_ACQUIRE_URL = "/api/v1/sections/{sid}/lock"
_CSRF_TOKEN = "test-csrf-token-for-ep17-force-release"


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
    """Seed two users + workspace + work_item + section. Returns dict of useful IDs."""
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
        # Holder user
        holder = User.from_google_claims(
            sub="force-release-holder-sub", email="holder@test.com", name="Holder", picture=None
        )
        await UserRepositoryImpl(session).upsert(holder)

        # Admin user (force-release caller)
        admin = User.from_google_claims(
            sub="force-release-admin-sub", email="admin@test.com", name="Admin", picture=None
        )
        await UserRepositoryImpl(session).upsert(admin)

        ws = Workspace.create_from_email(email="holder@test.com", created_by=holder.id)
        ws.slug = "force-release-test"
        await WorkspaceRepositoryImpl(session).create(ws)

        for uid in (holder.id, admin.id):
            await WorkspaceMembershipRepositoryImpl(session).create(
                WorkspaceMembership.create(
                    workspace_id=ws.id, user_id=uid, role="member", is_default=True
                )
            )

        wi = WorkItem.create(
            title="Force release test item",
            type=WorkItemType.TASK,
            owner_id=holder.id,
            creator_id=holder.id,
            project_id=ws.id,
        )
        await WorkItemRepositoryImpl(session).save(wi, ws.id)

        section = Section.create(
            work_item_id=wi.id,
            section_type=SectionType.SUMMARY,
            display_order=1,
            is_required=True,
            created_by=holder.id,
        )
        await SectionRepositoryImpl(session).save(section)
        await session.commit()

    await engine.dispose()

    return {
        "holder_id": holder.id,
        "admin_id": admin.id,
        "workspace_id": ws.id,
        "work_item_id": wi.id,
        "section_id": section.id,
        "holder_token": _make_token(holder.id, ws.id),
        "admin_token": _make_token(admin.id, ws.id, is_superadmin=True),
    }


def _auth_headers(token: str) -> dict:
    """Build headers that satisfy both auth (cookie) and CSRF (double-submit)."""
    cookie_header = f"access_token={token}; csrf_token={_CSRF_TOKEN}"
    return {
        "Cookie": cookie_header,
        "X-CSRF-Token": _CSRF_TOKEN,
    }


async def _acquire_lock(http: AsyncClient, section_id, token: str) -> None:
    url = _ACQUIRE_URL.format(sid=section_id)
    resp = await http.post(url, headers=_auth_headers(token))
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# 1. force-release with reason → audit event includes reason in context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_release_with_reason_persists_to_audit_event(http, seeded, migrated_database):
    """RED: force-release with reason → audit_event.context contains reason"""
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])

    # Force release with reason
    resp = await http.post(
        _FORCE_RELEASE_URL.format(sid=seeded["section_id"]),
        json={"reason": "Conflicting edit detected"},
        headers=_auth_headers(seeded["admin_token"]),
    )
    assert resp.status_code == 200, resp.text

    # Verify audit event was persisted with reason in context
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from sqlalchemy import select
        from app.infrastructure.persistence.models.orm import AuditEventORM

        result = await session.execute(
            select(AuditEventORM)
            .where(AuditEventORM.action == "force_released_section_lock")
            .order_by(AuditEventORM.created_at.desc())
        )
        events = result.scalars().all()
        assert len(events) > 0
        event = events[0]
        assert event.context.get("reason") == "Conflicting edit detected"

    await engine.dispose()


# ---------------------------------------------------------------------------
# 2. force-release without reason → audit event has reason=None
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_force_release_without_reason_persists_none_to_audit_event(http, seeded, migrated_database):
    """RED: force-release without reason → audit_event.context has reason=None"""
    await _acquire_lock(http, seeded["section_id"], seeded["holder_token"])

    # Force release without reason (optional field)
    resp = await http.post(
        _FORCE_RELEASE_URL.format(sid=seeded["section_id"]),
        json={},
        headers=_auth_headers(seeded["admin_token"]),
    )
    assert resp.status_code == 200, resp.text

    # Verify audit event was persisted with reason=None in context
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        from sqlalchemy import select
        from app.infrastructure.persistence.models.orm import AuditEventORM

        result = await session.execute(
            select(AuditEventORM)
            .where(AuditEventORM.action == "force_released_section_lock")
            .order_by(AuditEventORM.created_at.desc())
        )
        events = result.scalars().all()
        assert len(events) > 0
        event = events[0]
        assert event.context.get("reason") is None

    await engine.dispose()
