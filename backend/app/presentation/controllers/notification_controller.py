"""EP-08 — Notification controller.

Routes:
  GET   /api/v1/notifications
  PATCH /api/v1/notifications/{notification_id}/read
  PATCH /api/v1/notifications/{notification_id}/actioned
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.team_service import (
    NotificationNotFoundError,
    NotificationService,
)
from app.presentation.dependencies import get_current_user, get_notification_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _notification_payload(n: Any) -> dict[str, Any]:
    return {
        "id": str(n.id),
        "workspace_id": str(n.workspace_id),
        "recipient_id": str(n.recipient_id),
        "type": n.type,
        "state": n.state.value,
        "actor_id": str(n.actor_id) if n.actor_id else None,
        "subject_type": n.subject_type,
        "subject_id": str(n.subject_id),
        "deeplink": n.deeplink,
        "quick_action": n.quick_action,
        "extra": n.extra,
        "created_at": n.created_at.isoformat(),
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "actioned_at": n.actioned_at.isoformat() if n.actioned_at else None,
    }


@router.get("/notifications")
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    result = await service.list_inbox(
        user_id=current_user.id,
        workspace_id=current_user.workspace_id,
        page=page,
        page_size=page_size,
    )
    return _ok(
        {
            "items": [_notification_payload(n) for n in result.items],
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
        }
    )


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        notification = await service.mark_read(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_notification_payload(notification))


@router.patch("/notifications/{notification_id}/actioned")
async def mark_actioned(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        notification = await service.mark_actioned(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_notification_payload(notification))
