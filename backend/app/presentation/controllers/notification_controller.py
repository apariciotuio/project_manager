"""EP-08 — Notification controller.

Routes:
  GET   /api/v1/notifications                      — list (user-scoped, paginated)
  GET   /api/v1/notifications/unread-count          — badge count
  POST  /api/v1/notifications/mark-all-read         — bulk mark read
  PATCH /api/v1/notifications/{notification_id}/read
  PATCH /api/v1/notifications/{notification_id}/actioned

IDOR: all mutation endpoints verify notification.recipient_id == current_user.id
before taking action. Unauthorized access returns 404 (not 403) to avoid leaking
the existence of the notification.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from fastapi.responses import StreamingResponse

from app.application.services.notification_service import ExtendedNotificationService
from app.application.services.team_service import (
    NotificationNotFoundError,
    NotificationService,
    StaleActionError,
)
from app.infrastructure.pagination import InvalidCursorError, PaginationCursor
from app.infrastructure.sse.pg_notification_bus import PgNotificationBus
from app.infrastructure.sse.sse_handler import SseHandler
from app.presentation.dependencies import (
    get_current_user,
    get_extended_notification_service,
    get_jwt_adapter,
    get_notification_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications"])

_STREAM_TOKEN_TTL_SECONDS = 300  # 5 minutes
_SSE_NOTIFICATION_CHANNEL_PREFIX = "sse:notification:"

_NOT_FOUND_DETAIL = {
    "error": {"code": "NOT_FOUND", "message": "notification not found", "details": {}}
}


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


def _require_workspace(current_user: CurrentUser) -> UUID:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    return current_user.workspace_id


@router.get("/notifications")
async def list_notifications(
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)

    decoded_cursor: PaginationCursor | None = None
    if cursor is not None:
        try:
            decoded_cursor = PaginationCursor.decode(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CURSOR", "message": str(exc), "details": {}}},
            ) from exc

    result = await service.list_inbox_cursor(
        user_id=current_user.id,
        workspace_id=workspace_id,
        cursor=decoded_cursor,
        page_size=page_size,
    )
    return _ok(
        {
            "items": [_notification_payload(n) for n in result.rows],
            "pagination": {
                "cursor": result.next_cursor,
                "has_next": result.has_next,
            },
        }
    )


@router.get("/notifications/unread-count")
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    service: ExtendedNotificationService = Depends(get_extended_notification_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    count = await service.unread_count(user_id=current_user.id, workspace_id=workspace_id)
    return _ok({"count": count})


@router.post("/notifications/mark-all-read")
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    service: ExtendedNotificationService = Depends(get_extended_notification_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    updated = await service.mark_all_read(user_id=current_user.id, workspace_id=workspace_id)
    return _ok({"updated_count": updated})


@router.patch("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        notification = await service.mark_read(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        ) from exc
    # IDOR check: only the recipient can mark their own notification read
    if notification.recipient_id != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )
    return _ok(_notification_payload(notification))


@router.patch("/notifications/{notification_id}/actioned")
async def mark_actioned(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        notification = await service.mark_actioned(notification_id)
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        ) from exc
    # IDOR check
    if notification.recipient_id != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        )
    return _ok(_notification_payload(notification))


@router.post("/notifications/{notification_id}/action")
async def execute_action(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, Any]:
    """Execute a quick action on a notification.

    Returns 409 STALE_ACTION when the notification is already actioned.
    """
    _require_workspace(current_user)
    try:
        result = await service.execute_action(
            notification_id=notification_id,
            actor_id=current_user.id,
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=_NOT_FOUND_DETAIL,
        ) from exc
    except StaleActionError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "STALE_ACTION", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(result)


# ---------------------------------------------------------------------------
# SSE notifications stream
# ---------------------------------------------------------------------------


@router.post("/notifications/stream-token")
async def get_stream_token(
    current_user: CurrentUser = Depends(get_current_user),
    jwt_adapter=Depends(get_jwt_adapter),
) -> dict[str, Any]:
    """Issue a short-lived (5-minute) JWT for authenticating the SSE stream.

    The token carries the user_id and workspace_id so the stream endpoint
    can validate identity without reading cookies (EventSource doesn't send
    cookies cross-origin in all browsers).
    """
    _require_workspace(current_user)
    payload = {
        "sub": str(current_user.id),
        "workspace_id": str(current_user.workspace_id),
        "purpose": "sse_notifications",
        "exp": int(time.time()) + _STREAM_TOKEN_TTL_SECONDS,
    }
    token = jwt_adapter.encode(payload)
    return _ok({"token": token, "expires_in": _STREAM_TOKEN_TTL_SECONDS})


@router.get("/notifications/stream")
async def stream_notifications(
    token: str = Query(..., description="Short-lived stream token from /stream-token"),
    jwt_adapter=Depends(get_jwt_adapter),
) -> StreamingResponse:
    """SSE stream for real-time inbox updates.

    Events:
      notification_created  — new notification for the user
      inbox_count_updated   — per-tier counts changed

    Auth: requires a valid short-lived token from POST /notifications/stream-token.
    Returns 401 when token is missing, expired, or invalid.
    """
    from app.infrastructure.adapters.jwt_adapter import TokenExpiredError, TokenInvalidError

    try:
        claims = jwt_adapter.decode(token)
    except (TokenExpiredError, TokenInvalidError) as exc:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_STREAM_TOKEN", "message": str(exc), "details": {}}},
        ) from exc

    if claims.get("purpose") != "sse_notifications":
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {
                    "code": "INVALID_STREAM_TOKEN",
                    "message": "wrong token purpose",
                    "details": {},
                }
            },
        )

    user_id = claims["sub"]
    channel = f"{_SSE_NOTIFICATION_CHANNEL_PREFIX}{user_id}"

    from app.config.settings import get_settings

    db_url = get_settings().database.url.replace("postgresql+asyncpg://", "postgresql://")
    bus = PgNotificationBus(dsn=db_url)
    handler = SseHandler(bus)
    return handler.stream(channel)
