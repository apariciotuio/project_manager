"""SQLAlchemy implementation of IGapFindingRepository — EP-03."""
from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.gap_finding import StoredGapFinding
from app.domain.repositories.gap_finding_repository import IGapFindingRepository
from app.infrastructure.persistence.mappers.gap_finding_mapper import to_domain, to_orm
from app.infrastructure.persistence.models.orm import GapFindingORM


class GapFindingRepositoryImpl(IGapFindingRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_many(self, findings: list[StoredGapFinding]) -> list[StoredGapFinding]:
        if not findings:
            return []
        rows = [to_orm(f) for f in findings]
        for row in rows:
            self._session.add(row)
        await self._session.flush()
        return [to_domain(r) for r in rows]

    async def get_active_for_work_item(
        self,
        work_item_id: UUID,
        source: str | None = None,
    ) -> list[StoredGapFinding]:
        stmt = select(GapFindingORM).where(
            GapFindingORM.work_item_id == work_item_id,
            GapFindingORM.invalidated_at.is_(None),
        )
        if source is not None:
            stmt = stmt.where(GapFindingORM.source == source)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_domain(r) for r in rows]

    async def invalidate_for_work_item(
        self,
        work_item_id: UUID,
        now: datetime,
        source: str | None = None,
    ) -> int:
        conditions = [
            GapFindingORM.work_item_id == work_item_id,
            GapFindingORM.invalidated_at.is_(None),
        ]
        if source is not None:
            conditions.append(GapFindingORM.source == source)
        stmt = update(GapFindingORM).where(*conditions).values(invalidated_at=now)
        cursor = await self._session.execute(stmt)
        await self._session.flush()
        return int(cast(CursorResult[tuple[object, ...]], cursor).rowcount)
