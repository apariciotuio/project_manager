"""EP-09 — PersonDashboardService.

Aggregates per-user metrics: owned items by state, pending reviews,
inbox (unread notifications), overload indicator.
Redis cache TTL 120s per user.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.cache import ICache
from app.infrastructure.persistence.models.orm import (
    NotificationORM,
    ReviewRequestORM,
    WorkItemORM,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # seconds
_OVERLOAD_THRESHOLD = 5  # >5 items in in_clarification = overloaded


class PersonDashboardService:
    def __init__(self, session: AsyncSession, cache: ICache) -> None:
        self._session = session
        self._cache = cache

    async def get_metrics(self, user_id: UUID, *, workspace_id: UUID) -> dict[str, Any]:
        cache_key = f"dashboard:person:{user_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        data = await self._compute(user_id, workspace_id)
        await self._cache.set(cache_key, json.dumps(data, default=str), _CACHE_TTL)
        return data

    async def invalidate(self, user_id: UUID) -> None:
        await self._cache.delete(f"dashboard:person:{user_id}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _compute(self, user_id: UUID, workspace_id: UUID) -> dict[str, Any]:
        # Items owned by this user, grouped by state (no archived)
        state_stmt = (
            select(
                WorkItemORM.state,
                func.count(WorkItemORM.id).label("cnt"),
            )
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.owner_id == user_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .group_by(WorkItemORM.state)
        )
        state_rows = (await self._session.execute(state_stmt)).all()

        owned_by_state: dict[str, int] = {}
        for row in state_rows:
            owned_by_state[row.state] = row.cnt

        in_clarification_count = owned_by_state.get("in_clarification", 0)
        overloaded = in_clarification_count > _OVERLOAD_THRESHOLD

        # Pending review requests where this user is the reviewer
        reviews_stmt = (
            select(func.count(ReviewRequestORM.id))
            .where(
                ReviewRequestORM.reviewer_id == user_id,
                ReviewRequestORM.status == "pending",
            )
        )
        pending_reviews_count: int = (
            (await self._session.execute(reviews_stmt)).scalar() or 0
        )

        # Unread notification count (inbox)
        notif_stmt = (
            select(func.count(NotificationORM.id))
            .where(
                NotificationORM.recipient_id == user_id,
                NotificationORM.workspace_id == workspace_id,
                NotificationORM.read_at.is_(None),
                NotificationORM.archived_at.is_(None),
            )
        )
        inbox_count: int = (await self._session.execute(notif_stmt)).scalar() or 0

        return {
            "owned_by_state": owned_by_state,
            "overloaded": overloaded,
            "pending_reviews_count": int(pending_reviews_count),
            "inbox_count": int(inbox_count),
        }
