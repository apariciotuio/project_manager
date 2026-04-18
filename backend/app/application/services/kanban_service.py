"""EP-09 — KanbanService.

Grouped work-item board with per-column cursor pagination.
group_by: state | owner | tag | parent
Redis cache TTL 30s.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.cache import ICache
from app.infrastructure.persistence.models.orm import WorkItemORM

logger = logging.getLogger(__name__)

_CACHE_TTL = 30
_MAX_LIMIT = 25

FSM_ORDER = [
    "draft",
    "in_clarification",
    "in_review",
    "partially_validated",
    "ready",
]
EXCLUDED_STATES = {"archived", "blocked"}
VALID_GROUP_BY = {"state", "owner", "tag", "parent"}


class KanbanService:
    def __init__(self, session: AsyncSession, cache: ICache) -> None:
        self._session = session
        self._cache = cache

    async def get_board(
        self,
        *,
        workspace_id: UUID,
        group_by: str = "state",
        project_id: UUID | None = None,
        limit: int = 25,
        cursors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if limit > _MAX_LIMIT:
            raise ValueError(f"limit must be <= {_MAX_LIMIT}")
        if group_by not in VALID_GROUP_BY:
            raise ValueError(f"group_by must be one of: {sorted(VALID_GROUP_BY)}")

        # Cache key: kanban:{workspace_id}:{group_by}:{sha256(sorted params)}
        # project_id and limit MUST be in the hash — omitting them causes cross-project cache leaks.
        raw = json.dumps(
            {
                "group_by": group_by,
                "project_id": str(project_id) if project_id else None,
                "limit": limit,
            },
            sort_keys=True,
        ).encode()
        filter_hash = hashlib.sha256(raw).hexdigest()
        cache_key = f"kanban:{workspace_id}:{group_by}:{filter_hash}"

        cached = await self._cache.get(cache_key)
        if cached is not None:
            return json.loads(cached)

        strategy = {
            "state": self._group_by_state,
            "owner": self._group_by_owner,
            "tag": self._group_by_tag,
            "parent": self._group_by_parent,
        }[group_by]

        data = await strategy(
            workspace_id=workspace_id,
            project_id=project_id,
            limit=limit,
            cursors=cursors or {},
        )
        data["group_by"] = group_by

        await self._cache.set(cache_key, json.dumps(data, default=str), _CACHE_TTL)
        return data

    # ------------------------------------------------------------------
    # Group-by strategies
    # ------------------------------------------------------------------

    async def _group_by_state(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        limit: int,
        cursors: dict[str, str],
    ) -> dict[str, Any]:
        stmt = (
            select(WorkItemORM)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
                WorkItemORM.state.in_(FSM_ORDER),
            )
            .order_by(WorkItemORM.state, WorkItemORM.updated_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == project_id)

        rows = (await self._session.execute(stmt)).scalars().all()

        # Group by state and cap
        buckets: dict[str, list[Any]] = {s: [] for s in FSM_ORDER}
        counts: dict[str, int] = {s: 0 for s in FSM_ORDER}
        for item in rows:
            state = item.state
            if state not in FSM_ORDER:
                continue
            counts[state] += 1
            if len(buckets[state]) < limit:
                buckets[state].append(_card(item))

        columns = [
            {
                "key": state,
                "label": _label(state),
                "total_count": counts[state],
                "cards": buckets[state],
                "next_cursor": None,  # simplified: no cursor pagination in first pass
            }
            for state in FSM_ORDER
        ]
        return {"columns": columns}

    async def _group_by_owner(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        limit: int,
        cursors: dict[str, str],
    ) -> dict[str, Any]:
        stmt = (
            select(WorkItemORM)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .order_by(WorkItemORM.updated_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == project_id)

        rows = (await self._session.execute(stmt)).scalars().all()

        buckets: dict[str, list[Any]] = {}
        counts: dict[str, int] = {}
        for item in rows:
            key = str(item.owner_id) if item.owner_id else "unowned"
            counts[key] = counts.get(key, 0) + 1
            if key not in buckets:
                buckets[key] = []
            if len(buckets[key]) < limit:
                buckets[key].append(_card(item))

        columns = [
            {
                "key": key,
                "label": key if key != "unowned" else "Unowned",
                "total_count": counts[key],
                "cards": cards,
                "next_cursor": None,
            }
            for key, cards in buckets.items()
        ]
        return {"columns": columns}

    async def _group_by_tag(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        limit: int,
        cursors: dict[str, str],
    ) -> dict[str, Any]:
        stmt = (
            select(WorkItemORM)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .order_by(WorkItemORM.updated_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == project_id)

        rows = (await self._session.execute(stmt)).scalars().all()

        buckets: dict[str, list[Any]] = {}
        counts: dict[str, int] = {}
        for item in rows:
            tags = item.tags or []
            if not tags:
                tags = ["untagged"]
            for tag in tags:
                counts[tag] = counts.get(tag, 0) + 1
                if tag not in buckets:
                    buckets[tag] = []
                if len(buckets[tag]) < limit:
                    buckets[tag].append(_card(item))

        columns = [
            {
                "key": key,
                "label": key if key != "untagged" else "Untagged",
                "total_count": counts[key],
                "cards": cards,
                "next_cursor": None,
            }
            for key, cards in buckets.items()
        ]
        return {"columns": columns}

    async def _group_by_parent(
        self,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        limit: int,
        cursors: dict[str, str],
    ) -> dict[str, Any]:
        stmt = (
            select(WorkItemORM)
            .where(
                WorkItemORM.workspace_id == workspace_id,
                WorkItemORM.deleted_at.is_(None),
            )
            .order_by(WorkItemORM.updated_at.desc())
        )
        if project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == project_id)

        rows = (await self._session.execute(stmt)).scalars().all()

        buckets: dict[str, list[Any]] = {}
        counts: dict[str, int] = {}
        for item in rows:
            key = str(item.parent_work_item_id) if item.parent_work_item_id else "no_parent"
            counts[key] = counts.get(key, 0) + 1
            if key not in buckets:
                buckets[key] = []
            if len(buckets[key]) < limit:
                buckets[key].append(_card(item))

        columns = [
            {
                "key": key,
                "label": key if key != "no_parent" else "No parent",
                "total_count": counts[key],
                "cards": cards,
                "next_cursor": None,
            }
            for key, cards in buckets.items()
        ]
        return {"columns": columns}


def _card(item: WorkItemORM) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "title": item.title,
        "type": item.type,
        "state": item.state,
        "owner_id": str(item.owner_id) if item.owner_id else None,
        "completeness_score": item.completeness_score,
        "attachment_count": getattr(item, "attachment_count", 0),
        "tag_ids": getattr(item, "tags", []) or [],
    }


def _label(state: str) -> str:
    return state.replace("_", " ").title()
