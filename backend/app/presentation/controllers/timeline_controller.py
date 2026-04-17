"""EP-07 — Timeline controller.

Routes:
  GET /api/v1/work-items/{id}/timeline
      ?cursor=&limit=50&event_types=&actor_types=&from_date=&to_date=

Response shape matches EP-03 frontend useTimeline hook:
  { data: { events: [...], has_more: bool, next_cursor: str | null } }
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.timeline_service import TimelineService
from app.domain.models.timeline_event import TimelineEvent
from app.presentation.dependencies import get_current_user, get_timeline_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["timeline"])

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


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


@router.get("/work-items/{work_item_id}/timeline")
async def get_timeline(
    work_item_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT),
    event_types: list[str] | None = Query(default=None),
    actor_types: list[str] | None = Query(default=None),
    from_date: datetime | None = Query(default=None),
    to_date: datetime | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    svc: TimelineService = Depends(get_timeline_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    try:
        result = await svc.list_events(
            work_item_id=work_item_id,
            workspace_id=current_user.workspace_id,
            cursor=cursor,
            limit=limit,
            event_types=event_types,
            actor_types=actor_types,
            from_date=from_date,
            to_date=to_date,
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={
                "error": {
                    "code": "INVALID_CURSOR",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc

    return {
        "data": {
            "events": [_event_payload(e) for e in result["events"]],
            "has_more": result["has_more"],
            "next_cursor": result["next_cursor"],
        }
    }
