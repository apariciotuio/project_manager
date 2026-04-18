"""EP-09 — Dashboard controller.

GET /api/v1/workspaces/dashboard
GET /api/v1/dashboards/person/{user_id}
GET /api/v1/dashboards/team/{team_id}
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.dashboard_service import DashboardService
from app.application.services.person_dashboard_service import PersonDashboardService
from app.application.services.team_dashboard_service import TeamDashboardService
from app.presentation.dependencies import (
    get_current_user,
    get_dashboard_service,
    get_person_dashboard_service,
    get_team_dashboard_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser

router = APIRouter(tags=["dashboard"])


def _require_workspace(current_user: CurrentUser) -> UUID:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
    return current_user.workspace_id


@router.get("/workspaces/dashboard")
async def get_workspace_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> dict[str, Any]:
    """Workspace-scoped dashboard aggregations. Cached 60s per workspace."""
    workspace_id = _require_workspace(current_user)
    data = await service.get_workspace_dashboard(workspace_id)
    return {"data": data, "message": "ok"}


@router.get("/dashboards/person/{user_id}")
async def get_person_dashboard(
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: PersonDashboardService = Depends(get_person_dashboard_service),
) -> dict[str, Any]:
    """Per-user aggregations. Caller must be the owner or a superadmin.

    404 is not returned for unknown user_id — RLS scopes to workspace so
    zero-item users return empty aggregations (200 with empty owned_by_state).
    """
    workspace_id = _require_workspace(current_user)
    if user_id != current_user.id and not current_user.is_superadmin:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "cannot view another user's dashboard",
                    "details": {},
                }
            },
        )
    data = await service.get_metrics(user_id, workspace_id=workspace_id)
    return {"data": data, "message": "ok"}


@router.get("/dashboards/team/{team_id}")
async def get_team_dashboard(
    team_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamDashboardService = Depends(get_team_dashboard_service),
) -> dict[str, Any]:
    """Team aggregations. AuthZ: any workspace member can view team stats.

    404 is not surfaced here — if the team has no members in this workspace
    the result is empty aggregations. Team existence is validated by the team
    service separately.
    """
    workspace_id = _require_workspace(current_user)
    data = await service.get_metrics(team_id, workspace_id=workspace_id)
    return {"data": data, "message": "ok"}
