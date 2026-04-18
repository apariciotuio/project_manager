"""EP-08 Group C — Inbox controller.

Routes:
  GET /api/v1/inbox          — tiered inbox (user-scoped, optional type filter)
  GET /api/v1/inbox/count    — per-tier counts + total

Auth: all endpoints require a valid session with workspace_id.
IDOR: InboxService only returns items belonging to the authenticated user.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.inbox_service import InboxService
from app.presentation.dependencies import get_current_user, get_inbox_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["inbox"])


def _require_workspace(current_user: CurrentUser) -> UUID:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    return current_user.workspace_id


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/inbox")
async def get_inbox(
    item_type: str | None = Query(default=None, description="Filter by work item type"),
    current_user: CurrentUser = Depends(get_current_user),
    service: InboxService = Depends(get_inbox_service),
) -> dict[str, Any]:
    """Return the tiered inbox for the authenticated user."""
    workspace_id = _require_workspace(current_user)
    result = await service.get_inbox(
        user_id=current_user.id,
        workspace_id=workspace_id,
        item_type=item_type,
    )
    return _ok(result)


@router.get("/inbox/count")
async def get_inbox_count(
    item_type: str | None = Query(default=None, description="Filter by work item type"),
    current_user: CurrentUser = Depends(get_current_user),
    service: InboxService = Depends(get_inbox_service),
) -> dict[str, Any]:
    """Return per-tier item counts for the authenticated user."""
    workspace_id = _require_workspace(current_user)
    result = await service.get_counts(
        user_id=current_user.id,
        workspace_id=workspace_id,
        item_type=item_type,
    )
    return _ok(result)
