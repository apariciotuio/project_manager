"""EP-09 — DashboardService.

On-demand aggregations + Redis cache (TTL 60s per workspace).
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.cache import ICache
from app.infrastructure.persistence.models.orm import TimelineEventORM, WorkItemORM

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # seconds — per EP-12 design.md cache key table


class DashboardService:
    def __init__(self, session: AsyncSession, cache: ICache) -> None:
        self._session = session
        self._cache = cache

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    async def get_workspace_dashboard(self, workspace_id: UUID) -> dict[str, Any]:
        cache_key = f"dashboard:workspace:{workspace_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        data = await self._compute_workspace_dashboard(workspace_id)
        await self._cache.set(cache_key, json.dumps(data, default=str), _CACHE_TTL)
        return data

    async def invalidate(self, workspace_id: UUID) -> None:
        await self._cache.delete(f"dashboard:workspace:{workspace_id}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _compute_workspace_dashboard(self, workspace_id: UUID) -> dict[str, Any]:
        # Aggregate by state
        state_stmt = (
            select(
                WorkItemORM.state,
                func.count(WorkItemORM.id).label("cnt"),
                func.avg(WorkItemORM.completeness_score).label("avg_completeness"),
            )
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .group_by(WorkItemORM.state)
        )
        state_rows = (await self._session.execute(state_stmt)).all()

        total = 0
        by_state: dict[str, int] = {}
        for row in state_rows:
            by_state[row.state] = row.cnt
            total += row.cnt

        # Aggregate by type
        type_stmt = (
            select(
                WorkItemORM.type,
                func.count(WorkItemORM.id).label("cnt"),
            )
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .group_by(WorkItemORM.type)
        )
        type_rows = (await self._session.execute(type_stmt)).all()
        by_type: dict[str, int] = {row.type: row.cnt for row in type_rows}

        # Average completeness across all items
        avg_stmt = select(func.avg(WorkItemORM.completeness_score)).where(
            WorkItemORM.workspace_id == workspace_id,
            WorkItemORM.deleted_at.is_(None),
        )
        avg_completeness = (await self._session.execute(avg_stmt)).scalar() or 0.0

        # 10 most recent timeline events
        timeline_stmt = (
            select(TimelineEventORM)
            .where(TimelineEventORM.workspace_id == workspace_id)
            .order_by(TimelineEventORM.occurred_at.desc())
            .limit(10)
        )
        timeline_rows = (await self._session.execute(timeline_stmt)).scalars().all()
        recent_activity = [
            {
                "id": str(r.id),
                "work_item_id": str(r.work_item_id),
                "event_type": r.event_type,
                "actor_id": str(r.actor_id) if r.actor_id else None,
                "actor_display_name": r.actor_display_name,
                "summary": r.summary,
                "occurred_at": r.occurred_at.isoformat(),
            }
            for r in timeline_rows
        ]

        return {
            "work_items": {
                "total": total,
                "by_state": by_state,
                "by_type": by_type,
                "avg_completeness": round(float(avg_completeness), 2),
            },
            "recent_activity": recent_activity,
        }
