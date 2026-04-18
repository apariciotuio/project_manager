"""EP-10 — Admin dashboard controller.

Routes:
  GET /api/v1/admin/dashboard
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.admin_dashboard_service import AdminDashboardService
from app.presentation.dependencies import get_cache_adapter, get_db_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def get_dashboard_service(
    session: AsyncSession = Depends(get_db_session),
    cache: Any = Depends(get_cache_adapter),
) -> AdminDashboardService:
    return AdminDashboardService(session=session, cache=cache)


@router.get("")
async def get_admin_dashboard(
    project_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_admin),
    service: AdminDashboardService = Depends(get_dashboard_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    data = await service.get_dashboard(current_user.workspace_id, project_id)
    return _ok(data)
