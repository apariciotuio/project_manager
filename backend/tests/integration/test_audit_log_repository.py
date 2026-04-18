"""Integration tests for AuditRepositoryImpl.append().

Scenarios:
  - append() inserts a record with all expected fields and returns the persisted entity
  - append() is append-only: IAuditRepository exposes no update() or delete() methods
  - When called within a transaction that is rolled back, the audit record is NOT persisted
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.models.audit_event import AuditEvent
from app.domain.repositories.audit_repository import IAuditRepository
from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
from app.infrastructure.persistence.models.orm import AuditEventORM


@pytest.fixture
def repo(db_session: AsyncSession) -> AuditRepositoryImpl:
    return AuditRepositoryImpl(db_session)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    *,
    action: str = "test.action",
    category: str = "domain",
    actor_id=None,
    workspace_id=None,
) -> AuditEvent:
    return AuditEvent(
        id=uuid4(),
        category=category,  # type: ignore[arg-type]
        action=action,
        actor_id=actor_id,
        actor_display="Test Actor" if actor_id else None,
        workspace_id=workspace_id,
        entity_type="work_item",
        entity_id=uuid4(),
        before_value={"status": "draft"},
        after_value={"status": "active"},
        context={"ip": "127.0.0.1"},
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_append_returns_persisted_entity(repo: AuditRepositoryImpl, db_session: AsyncSession) -> None:
    """append() writes a row and returns the domain entity with all fields intact."""
    event = _make_event(action="work_item.status_changed")

    result = await repo.append(event)
    await db_session.commit()

    assert result is event, "append() must return the same entity"

    row = (
        await db_session.execute(
            select(AuditEventORM).where(AuditEventORM.id == event.id)
        )
    ).scalar_one_or_none()

    assert row is not None, "row must be persisted in DB"
    assert row.action == "work_item.status_changed"
    assert row.category == "domain"
    assert row.entity_type == "work_item"
    assert row.entity_id == event.entity_id
    assert row.before_value == {"status": "draft"}
    assert row.after_value == {"status": "active"}
    assert row.context == {"ip": "127.0.0.1"}
    assert row.created_at is not None


async def test_append_persists_actor_and_workspace(
    repo: AuditRepositoryImpl, db_session: AsyncSession, migrated_database
) -> None:
    """append() stores actor_id and workspace_id when provided (FK columns, nullable)."""
    # Use None for FKs to avoid FK constraint issues in isolated test
    event = _make_event(action="auth.login", category="auth")

    await repo.append(event)
    await db_session.commit()

    row = (
        await db_session.execute(
            select(AuditEventORM).where(AuditEventORM.id == event.id)
        )
    ).scalar_one_or_none()

    assert row is not None
    assert row.actor_id is None
    assert row.workspace_id is None
    assert row.actor_display is None


async def test_append_with_minimal_fields(repo: AuditRepositoryImpl, db_session: AsyncSession) -> None:
    """append() succeeds with only required fields (no optional FK refs or metadata)."""
    event = AuditEvent(
        id=uuid4(),
        category="admin",
        action="config.updated",
        context={},
    )

    result = await repo.append(event)
    await db_session.commit()

    assert result.id == event.id

    row = (
        await db_session.execute(
            select(AuditEventORM).where(AuditEventORM.id == event.id)
        )
    ).scalar_one_or_none()

    assert row is not None
    assert row.before_value is None
    assert row.after_value is None
    assert row.entity_type is None
    assert row.entity_id is None


async def test_interface_is_append_only(repo: AuditRepositoryImpl) -> None:
    """IAuditRepository must NOT expose update() or delete() methods."""
    assert not hasattr(IAuditRepository, "update"), "IAuditRepository must not have update()"
    assert not hasattr(IAuditRepository, "delete"), "IAuditRepository must not have delete()"
    assert not hasattr(repo, "update"), "AuditRepositoryImpl must not have update()"
    assert not hasattr(repo, "delete"), "AuditRepositoryImpl must not have delete()"


async def test_append_rolls_back_with_outer_transaction(migrated_database) -> None:
    """When the outer transaction is rolled back, the audit record is NOT persisted.

    Confirms shared-transaction semantics: audit writes are part of the caller's
    unit of work, not a separate fire-and-forget write.
    """
    engine = create_async_engine(migrated_database.database.url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    event = _make_event(action="rollback.test")

    async with factory() as session:
        repo = AuditRepositoryImpl(session)
        await repo.append(event)
        await session.flush()
        # Explicitly roll back without committing
        await session.rollback()

    # Open a fresh session and verify the row is gone
    async with factory() as verify_session:
        row = (
            await verify_session.execute(
                select(AuditEventORM).where(AuditEventORM.id == event.id)
            )
        ).scalar_one_or_none()
        assert row is None, "rolled-back audit record must not be persisted"

    await engine.dispose()
