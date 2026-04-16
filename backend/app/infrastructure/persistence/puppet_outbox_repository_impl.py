"""EP-13 — Puppet sync outbox repository implementation."""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.models.orm import PuppetSyncOutboxORM

logger = logging.getLogger(__name__)


def _row_to_dict(row: PuppetSyncOutboxORM) -> dict[str, Any]:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "work_item_id": row.work_item_id,
        "operation": row.operation,
        "payload": dict(row.payload),
        "status": row.status,
        "attempts": row.attempts,
        "last_error": row.last_error,
        "enqueued_at": row.enqueued_at,
        "processed_at": row.processed_at,
    }


class PuppetOutboxRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        workspace_id: UUID,
        work_item_id: UUID,
        operation: str,
        payload: dict[str, Any],
    ) -> None:
        row = PuppetSyncOutboxORM()
        row.id = uuid4()
        row.workspace_id = workspace_id
        row.work_item_id = work_item_id
        row.operation = operation
        row.payload = payload
        row.status = "pending"
        row.attempts = 0
        row.last_error = None
        row.enqueued_at = datetime.now(UTC)
        row.processed_at = None
        self._session.add(row)
        await self._session.flush()
        logger.debug(
            "puppet_outbox.enqueue workspace=%s work_item=%s op=%s",
            workspace_id,
            work_item_id,
            operation,
        )

    async def claim_batch(self, limit: int = 50) -> list[dict[str, Any]]:
        """Atomically move up to `limit` pending rows to in_flight and return them.

        Uses a subquery + UPDATE ... RETURNING pattern so concurrent workers don't
        pick the same rows.
        """
        # Fetch pending rows first, then update them — SQLAlchemy async doesn't
        # support UPDATE...RETURNING portably across dialects, so we do two steps
        # inside the same transaction (safe because the session holds an exclusive
        # lock on the rows after the first SELECT FOR UPDATE SKIP LOCKED).
        stmt = (
            select(PuppetSyncOutboxORM)
            .where(PuppetSyncOutboxORM.status == "pending")
            .order_by(PuppetSyncOutboxORM.enqueued_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        if not rows:
            return []
        ids = [r.id for r in rows]
        await self._session.execute(
            update(PuppetSyncOutboxORM)
            .where(PuppetSyncOutboxORM.id.in_(ids))
            .values(status="in_flight", attempts=PuppetSyncOutboxORM.attempts + 1)
        )
        await self._session.flush()
        # Re-fetch to get updated state
        refreshed = (
            await self._session.execute(
                select(PuppetSyncOutboxORM).where(PuppetSyncOutboxORM.id.in_(ids))
            )
        ).scalars().all()
        return [_row_to_dict(r) for r in refreshed]

    async def mark_success(self, row_id: UUID) -> None:
        await self._session.execute(
            update(PuppetSyncOutboxORM)
            .where(PuppetSyncOutboxORM.id == row_id)
            .values(status="done", processed_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def mark_failed(self, row_id: UUID, error: str) -> None:
        await self._session.execute(
            update(PuppetSyncOutboxORM)
            .where(PuppetSyncOutboxORM.id == row_id)
            .values(
                status="failed",
                last_error=error,
                processed_at=datetime.now(UTC),
            )
        )
        await self._session.flush()
