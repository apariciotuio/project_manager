"""EP-10 — Admin support tools controller.

Routes:
  GET  /api/v1/admin/support/orphaned-work-items
  GET  /api/v1/admin/support/pending-invitations
  GET  /api/v1/admin/support/failed-exports
  GET  /api/v1/admin/support/config-blocked-work-items
  POST /api/v1/admin/support/reassign-owner
  POST /api/v1/admin/support/failed-exports/retry-all
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.admin_support_service import (
    AdminSupportService,
    ReassignTargetInactiveError,
    ReassignTerminalItemError,
    RetryAllRateLimitedError,
    SupportError,
)
from app.application.services.audit_service import AuditService
from app.presentation.dependencies import (
    get_audit_service,
    get_cache_adapter,
    get_db_session,
    require_admin,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/support", tags=["admin-support"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def get_support_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
    cache: Any = Depends(get_cache_adapter),
) -> AdminSupportService:
    return AdminSupportService(session=session, audit=audit, cache=cache)


@router.get("/orphaned-work-items")
async def get_orphaned_work_items(
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    items = await service.get_orphaned_work_items(current_user.workspace_id)
    return _ok(items)


@router.get("/pending-invitations")
async def get_pending_invitations(
    expiring_soon: bool = Query(default=False),
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    items = await service.get_pending_invitations(
        current_user.workspace_id, expiring_soon=expiring_soon
    )
    return _ok(items)


@router.get("/failed-exports")
async def get_failed_exports(
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    items = await service.get_failed_exports(current_user.workspace_id)
    return _ok(items)


@router.get("/config-blocked-work-items")
async def get_config_blocked_work_items(
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    result = await service.get_config_blocked_work_items(current_user.workspace_id)
    return _ok(result)


class ReassignOwnerRequest(BaseModel):
    work_item_id: UUID
    new_owner_id: UUID


@router.post("/reassign-owner", status_code=http_status.HTTP_200_OK)
async def reassign_owner(
    body: ReassignOwnerRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        await service.reassign_owner(
            current_user.workspace_id,
            body.work_item_id,
            body.new_owner_id,
            current_user.id,
        )
    except ReassignTargetInactiveError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "reassign_target_inactive", "message": str(exc), "details": {}}},
        ) from exc
    except ReassignTerminalItemError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "reassign_terminal_item", "message": str(exc), "details": {}}},
        ) from exc
    except SupportError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "SUPPORT_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({}, "owner reassigned")


@router.post("/failed-exports/retry-all", status_code=http_status.HTTP_202_ACCEPTED)
async def retry_all_failed_exports(
    current_user: CurrentUser = Depends(require_admin),
    service: AdminSupportService = Depends(get_support_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        result = await service.retry_all_failed_exports(
            current_user.workspace_id, current_user.id
        )
    except RetryAllRateLimitedError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": {"code": "retry_all_rate_limited", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(result, "retries queued")
