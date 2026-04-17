"""EP-07 — TimelineService: append events + cursor-paginated list.

Cursor is encoded as "occurred_at_iso|id" (pipe-delimited).
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.models.timeline_event import TimelineActorType, TimelineEvent
from app.domain.repositories.timeline_repository import ITimelineEventRepository

logger = logging.getLogger(__name__)


def _encode_cursor(event: TimelineEvent) -> str:
    return f"{event.occurred_at.isoformat()}|{event.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    ts_part, id_part = cursor.rsplit("|", 1)
    return datetime.fromisoformat(ts_part), UUID(id_part)


class TimelineService:
    def __init__(self, *, timeline_repo: ITimelineEventRepository) -> None:
        self._repo = timeline_repo

    async def append(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        event_type: str,
        actor_type: TimelineActorType,
        summary: str,
        actor_id: UUID | None = None,
        actor_display_name: str | None = None,
        payload: dict[str, Any] | None = None,
        source_id: UUID | None = None,
        source_table: str | None = None,
    ) -> TimelineEvent:
        event = TimelineEvent.create(
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            summary=summary,
            payload=payload,
            source_id=source_id,
            source_table=source_table,
        )
        return await self._repo.insert(event)

    async def list_events(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
        event_types: list[str] | None = None,
        actor_types: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> dict[str, Any]:
        before_occurred_at: datetime | None = None
        before_id: UUID | None = None

        if cursor:
            before_occurred_at, before_id = _decode_cursor(cursor)

        events = await self._repo.list_for_work_item(
            work_item_id,
            before_occurred_at=before_occurred_at,
            before_id=before_id,
            limit=limit + 1,  # fetch one extra to determine has_more
            event_types=event_types,
            actor_types=actor_types,
            from_date=from_date,
            to_date=to_date,
        )

        has_more = len(events) > limit
        if has_more:
            events = events[:limit]

        next_cursor: str | None = None
        if has_more and events:
            next_cursor = _encode_cursor(events[-1])

        return {
            "events": events,
            "has_more": has_more,
            "next_cursor": next_cursor,
        }
