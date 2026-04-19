"""EP-17 — SectionLock repository implementation."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.section_lock import SectionLock
from app.infrastructure.persistence.mappers.lock_mapper import lock_to_domain, lock_to_orm
from app.infrastructure.persistence.models.orm import SectionLockORM

logger = logging.getLogger(__name__)


class SectionLockRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def acquire(self, lock: SectionLock) -> SectionLock:
        """Upsert: insert new lock, or replace if existing one is expired.

        Uses ON CONFLICT DO UPDATE so the caller gets an atomic acquire-or-steal.
        The application layer checks expiry before calling this.
        """
        stmt = (
            insert(SectionLockORM)
            .values(
                id=lock.id,
                section_id=lock.section_id,
                work_item_id=lock.work_item_id,
                held_by=lock.held_by,
                acquired_at=lock.acquired_at,
                heartbeat_at=lock.heartbeat_at,
                expires_at=lock.expires_at,
            )
            .on_conflict_do_update(
                constraint="uq_section_lock_active",
                set_={
                    "id": lock.id,
                    "held_by": lock.held_by,
                    "acquired_at": lock.acquired_at,
                    "heartbeat_at": lock.heartbeat_at,
                    "expires_at": lock.expires_at,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return lock

    async def get(self, section_id: UUID) -> SectionLock | None:
        stmt = select(SectionLockORM).where(SectionLockORM.section_id == section_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return lock_to_domain(row) if row else None

    async def save(self, lock: SectionLock) -> SectionLock:
        existing = await self._session.get(SectionLockORM, lock.id)
        if existing is None:
            self._session.add(lock_to_orm(lock))
        else:
            existing.heartbeat_at = lock.heartbeat_at
            existing.expires_at = lock.expires_at
        await self._session.flush()
        return lock

    async def delete(self, section_id: UUID) -> None:
        await self._session.execute(
            delete(SectionLockORM).where(SectionLockORM.section_id == section_id)
        )
        await self._session.flush()

    async def get_locks_for_work_item(self, work_item_id: UUID) -> list[SectionLock]:
        stmt = (
            select(SectionLockORM)
            .where(SectionLockORM.work_item_id == work_item_id)
            .order_by(SectionLockORM.acquired_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [lock_to_domain(r) for r in rows]

    async def cleanup_expired(self) -> int:
        now = datetime.now(UTC)
        stmt = select(SectionLockORM).where(SectionLockORM.expires_at <= now)
        rows = (await self._session.execute(stmt)).scalars().all()
        count = len(rows)
        if rows:
            ids = [r.id for r in rows]
            await self._session.execute(
                delete(SectionLockORM).where(SectionLockORM.id.in_(ids))
            )
            await self._session.flush()
            logger.info("lock.cleanup_expired removed=%d", count)
        return count

    async def get_lock_info_by_work_item_ids(
        self, work_item_ids: list[UUID]
    ) -> dict[UUID, dict[str, int | UUID]]:
        """Fetch lock info for multiple work_items in a single query.

        Returns: {work_item_id: {"count": int, "held_by": UUID | None}, ...}
        Only includes work_items that have active locks.
        """
        if not work_item_ids:
            return {}

        stmt = (
            select(
                SectionLockORM.work_item_id,
                func.count(SectionLockORM.id).label("lock_count"),
                SectionLockORM.held_by,  # There's typically one lock per work_item, but group to be safe
            )
            .where(SectionLockORM.work_item_id.in_(work_item_ids))
            .group_by(SectionLockORM.work_item_id, SectionLockORM.held_by)
        )
        rows = (await self._session.execute(stmt)).all()

        result: dict[UUID, dict[str, int | UUID]] = {}
        for row in rows:
            result[row.work_item_id] = {
                "count": row.lock_count,
                "held_by": row.held_by,
            }
        return result
