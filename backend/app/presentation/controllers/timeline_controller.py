"""EP-07 — Timeline controller.

Routes:
  GET /api/v1/work-items/{id}/timeline?cursor=&limit=50
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.domain.models.timeline_event import TimelineEvent
from app.domain.repositories.timeline_repository import ITimelineEventRepository
from app.presentation.dependencies import get_current_user, get_timeline_repo
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["timeline"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _event_payload(e: TimelineEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "work_item_id": str(e.work_item_id),
        "workspace_id": str(e.workspace_id),
        "event_type": e.event_type,
        "actor_type": e.actor_type.value,
        "actor_id": str(e.actor_id) if e.actor_id else None,
        "actor_display_name": e.actor_display_name,
        "summary": e.summary,
        "payload": e.payload,
        "occurred_at": e.occurred_at.isoformat(),
        "source_id": str(e.source_id) if e.source_id else None,
        "source_table": e.source_table,
    }


def _build_cursor(event: TimelineEvent) -> str:
    """Encode the last event's (occurred_at, id) pair as an opaque cursor."""
    return f"{event.occurred_at.isoformat()}|{event.id}"


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode cursor back to (occurred_at, id)."""
    ts_part, id_part = cursor.rsplit("|", 1)
    return datetime.fromisoformat(ts_part), UUID(id_part)


@router.get("/work-items/{work_item_id}/timeline")
async def get_timeline(
    work_item_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    current_user: CurrentUser = Depends(get_current_user),
    repo: ITimelineEventRepository = Depends(get_timeline_repo),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    before_occurred_at: datetime | None = None
    before_id: UUID | None = None

    if cursor:
        try:
            before_occurred_at, before_id = _parse_cursor(cursor)
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": {
                        "code": "INVALID_CURSOR",
                        "message": "invalid cursor",
                        "details": {},
                    }
                },
            ) from exc

    events = await repo.list_for_work_item(
        work_item_id,
        before_occurred_at=before_occurred_at,
        before_id=before_id,
        limit=limit,
    )

    next_cursor: str | None = None
    if len(events) == limit:
        next_cursor = _build_cursor(events[-1])

    return _ok(
        {
            "events": [_event_payload(e) for e in events],
            "next_cursor": next_cursor,
        }
    )
