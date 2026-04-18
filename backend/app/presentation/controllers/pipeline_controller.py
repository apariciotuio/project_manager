"""EP-09 — Pipeline controller.

GET /api/v1/pipeline
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.pipeline_service import PipelineQueryService
from app.presentation.dependencies import get_current_user, get_pipeline_service
from app.presentation.middleware.auth_middleware import CurrentUser

router = APIRouter(tags=["pipeline"])


@router.get("/pipeline")
async def get_pipeline(
    project_id: UUID | None = None,
    team_id: UUID | None = None,
    owner_id: UUID | None = None,
    state: list[str] | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: PipelineQueryService = Depends(get_pipeline_service),
) -> dict[str, Any]:
    """Funnel view: counts per workflow state across workspace/project.

    Columns in FSM order: draft → in_clarification → in_review →
    partially_validated → ready. ARCHIVED excluded.
    Each column contains up to 20 items. Blocked items in separate lane.
    Response cached 30s per filter combination.
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )

    data = await service.get_pipeline(
        workspace_id=current_user.workspace_id,
        project_id=project_id,
        team_id=team_id,
        owner_id=owner_id,
        state=state,
    )
    return {"data": data, "message": "ok"}
