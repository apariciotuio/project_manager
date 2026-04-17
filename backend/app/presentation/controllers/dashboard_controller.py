"""EP-09 — Dashboard controller.

GET /api/v1/workspaces/dashboard
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.dashboard_service import DashboardService
from app.presentation.dependencies import get_current_user, get_dashboard_service
from app.presentation.middleware.auth_middleware import CurrentUser

router = APIRouter(tags=["dashboard"])


@router.get("/workspaces/dashboard")
async def get_workspace_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> dict[str, Any]:
    """Workspace-scoped dashboard aggregations. Cached 60s per workspace."""
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )
    data = await service.get_workspace_dashboard(current_user.workspace_id)
    return {"data": data, "message": "ok"}
