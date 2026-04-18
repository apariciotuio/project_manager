"""EP-09 — PipelineQueryService.

Returns funnel view: counts per workflow state + up to 20 items per column.
Redis cache TTL 30s, keyed by SHA-256 of sorted filter params.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.cache import ICache
from app.infrastructure.persistence.models.orm import TeamMembershipORM, WorkItemORM

logger = logging.getLogger(__name__)

_CACHE_TTL = 30  # seconds
_MAX_ITEMS_PER_COLUMN = 20

# Canonical FSM state order — archived excluded
FSM_ORDER = [
    "draft",
    "in_clarification",
    "in_review",
    "partially_validated",
    "ready",
]
EXCLUDED_STATES = {"archived"}


class PipelineQueryService:
    def __init__(self, session: AsyncSession, cache: ICache) -> None:
        self._session = session
        self._cache = cache

    async def get_pipeline(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None = None,
        team_id: UUID | None = None,
        owner_id: UUID | None = None,
        state: list[str] | None = None,
    ) -> dict[str, Any]:
        filter_params = {
            "workspace_id": str(workspace_id),
            "project_id": str(project_id) if project_id else None,
            "team_id": str(team_id) if team_id else None,
            "owner_id": str(owner_id) if owner_id else None,
            "state": sorted(state) if state else None,
        }
        # Deterministic SHA-256 of sorted filter params
        raw = json.dumps(filter_params, sort_keys=True).encode()
        filter_hash = hashlib.sha256(raw).hexdigest()
        cache_key = f"pipeline:{workspace_id}:{filter_hash}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        data = await self._compute(
            workspace_id=workspace_id,
            project_id=project_id,
            team_id=team_id,
            owner_id=owner_id,
            state_filter=state,
        )
        await self._cache.set(cache_key, json.dumps(data, default=str), _CACHE_TTL)
        return data

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _team_member_subq(self, team_id: UUID) -> object:
        """Subquery: user IDs who are active members of team_id."""
        return (
            select(TeamMembershipORM.user_id).where(
                TeamMembershipORM.team_id == team_id,
                TeamMembershipORM.removed_at.is_(None),
            )
        ).scalar_subquery()

    async def _compute(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        team_id: UUID | None,
        owner_id: UUID | None,
        state_filter: list[str] | None,
    ) -> dict[str, Any]:
        # Step 1: Aggregate counts + avg_age per state (single grouped query)
        agg_stmt = (
            select(
                WorkItemORM.state,
                func.count(WorkItemORM.id).label("cnt"),
                func.coalesce(
                    func.avg(
                        func.extract(
                            "epoch",
                            func.now() - WorkItemORM.updated_at,
                        )
                        / 86400.0
                    ),
                    0.0,
                ).label("avg_age_days"),
            )
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .group_by(WorkItemORM.state)
        )
        if project_id is not None:
            agg_stmt = agg_stmt.where(WorkItemORM.project_id == project_id)
        if team_id is not None:
            # MF-4: team_id must be applied as a WHERE filter, not just hashed for cache key.
            agg_stmt = agg_stmt.where(WorkItemORM.owner_id.in_(self._team_member_subq(team_id)))
        if owner_id is not None:
            agg_stmt = agg_stmt.where(WorkItemORM.owner_id == owner_id)
        if state_filter:
            agg_stmt = agg_stmt.where(WorkItemORM.state.in_(state_filter))

        agg_rows = (await self._session.execute(agg_stmt)).all()

        # Build state → aggregation map
        agg_map: dict[str, dict[str, Any]] = {}
        blocked_agg: dict[str, Any] | None = None
        for row in agg_rows:
            if row.state in EXCLUDED_STATES:
                continue
            entry = {
                "state": row.state,
                "count": row.cnt,
                "avg_age_days": round(float(row.avg_age_days), 2),
            }
            if row.state == "blocked":
                blocked_agg = entry
            else:
                agg_map[row.state] = entry

        # Step 2: Fetch up to MAX_ITEMS_PER_COLUMN items per non-blocked column
        active_states = list(FSM_ORDER)
        if state_filter:
            active_states = [s for s in active_states if s in state_filter]

        columns: list[dict[str, Any]] = []

        if active_states:
            item_stmt = (
                select(WorkItemORM)
                .where(
                    WorkItemORM.workspace_id == workspace_id,
                    WorkItemORM.deleted_at.is_(None),
                    WorkItemORM.state.in_(active_states),
                )
                .order_by(WorkItemORM.state, WorkItemORM.updated_at.desc())
            )
            if project_id is not None:
                item_stmt = item_stmt.where(WorkItemORM.project_id == project_id)
            if team_id is not None:
                item_stmt = item_stmt.where(
                    WorkItemORM.owner_id.in_(self._team_member_subq(team_id))
                )
            if owner_id is not None:
                item_stmt = item_stmt.where(WorkItemORM.owner_id == owner_id)

            item_rows = (await self._session.execute(item_stmt)).scalars().all()

            # Group by state and cap at MAX_ITEMS_PER_COLUMN
            items_by_state: dict[str, list[Any]] = {}
            for item in item_rows:
                bucket = items_by_state.setdefault(item.state, [])
                if len(bucket) < _MAX_ITEMS_PER_COLUMN:
                    bucket.append(_serialize_item(item))

            # Emit columns in FSM order
            for state in active_states:
                agg = agg_map.get(state, {"state": state, "count": 0, "avg_age_days": 0.0})
                columns.append(
                    {
                        "state": state,
                        "count": agg["count"],
                        "avg_age_days": agg["avg_age_days"],
                        "items": items_by_state.get(state, []),
                    }
                )

        # Blocked lane
        blocked_lane: list[dict[str, Any]] = []
        if blocked_agg is not None:
            blocked_stmt = (
                select(WorkItemORM)
                .where(
                    WorkItemORM.workspace_id == workspace_id,
                    WorkItemORM.deleted_at.is_(None),
                    WorkItemORM.state == "blocked",
                )
                .order_by(WorkItemORM.updated_at.desc())
                .limit(_MAX_ITEMS_PER_COLUMN)
            )
            if project_id is not None:
                blocked_stmt = blocked_stmt.where(WorkItemORM.project_id == project_id)
            blocked_items = (await self._session.execute(blocked_stmt)).scalars().all()
            blocked_lane = [_serialize_item(item) for item in blocked_items]

        return {"columns": columns, "blocked_lane": blocked_lane}


def _serialize_item(item: WorkItemORM) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "type": item.type,
        "state": item.state,
        "owner_id": str(item.owner_id),
        "completeness_score": item.completeness_score,
    }
