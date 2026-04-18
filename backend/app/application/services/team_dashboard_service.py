"""EP-09 — TeamDashboardService.

Aggregates team metrics: owned items by state, pending reviews,
velocity (ready transitions last 30d), blocked count.
Redis cache TTL 120s per team.

WorkItemORM has no direct team_id FK — items are scoped by workspace.
Team membership is resolved via TeamMembershipORM.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.cache import ICache
from app.infrastructure.persistence.models.orm import (
    ReviewRequestORM,
    TeamMembershipORM,
    WorkItemORM,
)

logger = logging.getLogger(__name__)

_CACHE_TTL = 120  # seconds


class TeamDashboardService:
    def __init__(self, session: AsyncSession, cache: ICache) -> None:
        self._session = session
        self._cache = cache

    async def get_metrics(self, team_id: UUID, *, workspace_id: UUID) -> dict[str, Any]:
        cache_key = f"dashboard:team:{team_id}"
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        data = await self._compute(team_id, workspace_id)
        await self._cache.set(cache_key, json.dumps(data, default=str), _CACHE_TTL)
        return data

    async def invalidate(self, team_id: UUID) -> None:
        await self._cache.delete(f"dashboard:team:{team_id}")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _compute(self, team_id: UUID, workspace_id: UUID) -> dict[str, Any]:
        # Subquery: user IDs who are active team members
        member_subq = (
            select(TeamMembershipORM.user_id).where(
                TeamMembershipORM.team_id == team_id,
                TeamMembershipORM.removed_at.is_(None),
            )
        ).scalar_subquery()

        # Items owned by team members, grouped by state
        state_stmt = (
            select(
                WorkItemORM.state,
                func.count(WorkItemORM.id).label("cnt"),
            )
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.owner_id.in_(member_subq),
                WorkItemORM.deleted_at.is_(None),
            )
            .group_by(WorkItemORM.state)
        )
        state_rows = (await self._session.execute(state_stmt)).all()
        owned_by_state: dict[str, int] = {row.state: row.cnt for row in state_rows}

        # Pending review requests where team_id is the reviewer (team-type)
        review_stmt = select(func.count(ReviewRequestORM.id)).where(
            ReviewRequestORM.team_id == team_id,
            ReviewRequestORM.reviewer_type == "team",
            ReviewRequestORM.status == "pending",
        )
        pending_reviews: int = (await self._session.execute(review_stmt)).scalar() or 0

        # recent_ready_items: items currently in 'ready' state that were updated in the last 30 days,
        # owned by team members. This is an APPROXIMATION — it counts items whose state is
        # currently 'ready' AND were updated recently, not true throughput (items that transitioned
        # TO 'ready' in the period). Items that moved past 'ready' or back are not counted.
        # Field is named 'recent_ready_items' to avoid implying it is a true velocity metric.
        cutoff = datetime.now(UTC) - timedelta(days=30)
        velocity_stmt = select(func.count(WorkItemORM.id)).where(
            WorkItemORM.workspace_id == workspace_id,
            WorkItemORM.owner_id.in_(member_subq),
            WorkItemORM.state == "ready",
            WorkItemORM.updated_at >= cutoff,
            WorkItemORM.deleted_at.is_(None),
        )
        recent_ready_items: int = (await self._session.execute(velocity_stmt)).scalar() or 0

        # Blocked count
        blocked_stmt = select(func.count(WorkItemORM.id)).where(
            WorkItemORM.workspace_id == workspace_id,
            WorkItemORM.owner_id.in_(member_subq),
            WorkItemORM.state == "blocked",
            WorkItemORM.deleted_at.is_(None),
        )
        blocked_count: int = (await self._session.execute(blocked_stmt)).scalar() or 0

        return {
            "owned_by_state": owned_by_state,
            "pending_reviews": int(pending_reviews),
            "recent_ready_items": int(recent_ready_items),
            "blocked_count": int(blocked_count),
        }
