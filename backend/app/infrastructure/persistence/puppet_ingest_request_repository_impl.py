"""EP-13 — PuppetIngestRequestRepositoryImpl."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.puppet_ingest_request import PuppetIngestRequest
from app.infrastructure.persistence.models.orm import PuppetIngestRequestORM

logger = logging.getLogger(__name__)


def _orm_to_domain(row: PuppetIngestRequestORM) -> PuppetIngestRequest:
    return PuppetIngestRequest(
        id=row.id,
        workspace_id=row.workspace_id,
        source_kind=row.source_kind,
        work_item_id=row.work_item_id,
        payload=dict(row.payload),
        status=row.status,
        puppet_doc_id=row.puppet_doc_id,
        attempts=row.attempts,
        last_error=row.last_error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        succeeded_at=row.succeeded_at,
    )


class PuppetIngestRequestRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, request: PuppetIngestRequest) -> None:
        existing = await self._session.get(PuppetIngestRequestORM, request.id)
        if existing is None:
            orm = PuppetIngestRequestORM()
            orm.id = request.id
            orm.workspace_id = request.workspace_id
            orm.source_kind = request.source_kind
            orm.work_item_id = request.work_item_id
            orm.payload = request.payload
            orm.status = request.status
            orm.puppet_doc_id = request.puppet_doc_id
            orm.attempts = request.attempts
            orm.last_error = request.last_error
            orm.created_at = request.created_at
            orm.updated_at = request.updated_at
            orm.succeeded_at = request.succeeded_at
            self._session.add(orm)
        else:
            existing.status = request.status
            existing.puppet_doc_id = request.puppet_doc_id
            existing.attempts = request.attempts
            existing.last_error = request.last_error
            existing.updated_at = request.updated_at
            existing.succeeded_at = request.succeeded_at
        await self._session.flush()

    async def get(self, request_id: UUID) -> PuppetIngestRequest | None:
        row = await self._session.get(PuppetIngestRequestORM, request_id)
        if row is None:
            return None
        return _orm_to_domain(row)

    async def claim_queued_batch(self, workspace_id: UUID, limit: int) -> list[PuppetIngestRequest]:
        """SELECT FOR UPDATE SKIP LOCKED pattern — safe for concurrent workers."""
        stmt = (
            select(PuppetIngestRequestORM)
            .where(
                PuppetIngestRequestORM.workspace_id == workspace_id,
                PuppetIngestRequestORM.status == "queued",
            )
            .order_by(PuppetIngestRequestORM.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        if not rows:
            return []
        ids = [r.id for r in rows]
        await self._session.execute(
            update(PuppetIngestRequestORM)
            .where(PuppetIngestRequestORM.id.in_(ids))
            .values(status="dispatched", updated_at=datetime.now(UTC))
        )
        await self._session.flush()
        # Re-fetch updated rows
        refreshed = (
            (
                await self._session.execute(
                    select(PuppetIngestRequestORM).where(PuppetIngestRequestORM.id.in_(ids))
                )
            )
            .scalars()
            .all()
        )
        return [_orm_to_domain(r) for r in refreshed]

    async def has_succeeded_for_work_item(self, work_item_id: UUID) -> bool:
        stmt = (
            select(PuppetIngestRequestORM.id)
            .where(
                PuppetIngestRequestORM.work_item_id == work_item_id,
                PuppetIngestRequestORM.status == "succeeded",
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar() is not None

    async def list_by_workspace(
        self,
        workspace_id: UUID,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[PuppetIngestRequest]:
        stmt = (
            select(PuppetIngestRequestORM)
            .where(PuppetIngestRequestORM.workspace_id == workspace_id)
            .order_by(PuppetIngestRequestORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(PuppetIngestRequestORM.status == status)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_orm_to_domain(r) for r in rows]
