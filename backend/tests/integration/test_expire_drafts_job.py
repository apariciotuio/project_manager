"""EP-02 Phase 7 — expire_work_item_drafts integration test.

Runs the async function against the real testcontainer DB. Asserts:
- expired drafts are deleted, active drafts untouched
- return count matches deleted rows
- empty / no-expired case returns 0
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.infrastructure.persistence.models.orm import WorkItemDraftORM
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl


@pytest_asyncio.fixture
async def clean_db(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE work_item_drafts, workspace_memberships, sessions, "
                "oauth_states, work_items, workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    yield engine
    await engine.dispose()

    db_module._engine = None
    db_module._session_factory = None


async def _seed_user(engine) -> User:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        repo = UserRepositoryImpl(s)
        user = User.from_google_claims(
            sub=f"sub-{uuid4()}", email=f"{uuid4()}@tuio.com", name="U", picture=None
        )
        saved = await repo.upsert(user)
        await s.commit()
    return saved


async def _seed_workspace(engine, *, created_by) -> Workspace:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        repo = WorkspaceRepositoryImpl(s)
        ws = Workspace.create_from_email(email=f"{uuid4().hex[:8]}@tuio.com", created_by=created_by)
        saved = await repo.create(ws)
        await s.commit()
    return saved


async def _seed_draft(engine, *, user_id, workspace_id, expires_at: datetime) -> None:
    """Seed a draft row directly via ORM so we can control expires_at."""
    now = datetime.now(UTC)
    row = WorkItemDraftORM()
    row.id = uuid4()
    row.user_id = user_id
    row.workspace_id = workspace_id
    row.data = {}  # type: ignore[assignment]
    row.local_version = 1
    row.incomplete = False
    row.created_at = now
    row.updated_at = now
    row.expires_at = expires_at

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        s.add(row)
        await s.commit()


async def _count_drafts(engine) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        result = await s.execute(text("SELECT COUNT(*) FROM work_item_drafts"))
        return result.scalar_one()


async def _seed_users(engine, n: int) -> list[User]:
    return [await _seed_user(engine) for _ in range(n)]


async def test_expire_drafts_deletes_only_expired(clean_db) -> None:
    users = await _seed_users(clean_db, 5)
    workspace = await _seed_workspace(clean_db, created_by=users[0].id)
    now = datetime.now(UTC)

    # 2 expired, 3 active — use distinct user_ids to satisfy (user_id, workspace_id) unique
    for user in users[:2]:
        await _seed_draft(
            clean_db,
            user_id=user.id,
            workspace_id=workspace.id,
            expires_at=now - timedelta(hours=1),
        )
    for user in users[2:]:
        await _seed_draft(
            clean_db,
            user_id=user.id,
            workspace_id=workspace.id,
            expires_at=now + timedelta(days=30),
        )

    from app.infrastructure.jobs.expire_drafts_task import expire_work_item_drafts

    deleted = await expire_work_item_drafts()
    assert deleted == 2
    assert await _count_drafts(clean_db) == 3


async def test_expire_drafts_returns_zero_on_empty_table(clean_db) -> None:  # noqa: ARG001 — pytest fixture dep
    from app.infrastructure.jobs.expire_drafts_task import expire_work_item_drafts

    assert await expire_work_item_drafts() == 0


async def test_expire_drafts_returns_zero_when_no_expired(clean_db) -> None:
    users = await _seed_users(clean_db, 2)
    workspace = await _seed_workspace(clean_db, created_by=users[0].id)
    now = datetime.now(UTC)
    for user in users:
        await _seed_draft(
            clean_db,
            user_id=user.id,
            workspace_id=workspace.id,
            expires_at=now + timedelta(days=30),
        )

    from app.infrastructure.jobs.expire_drafts_task import expire_work_item_drafts

    deleted = await expire_work_item_drafts()
    assert deleted == 0
    assert await _count_drafts(clean_db) == 2
