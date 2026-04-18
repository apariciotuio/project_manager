"""EP-09 — Kanban controller.

GET /api/v1/work-items/kanban
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status

from app.application.services.kanban_service import KanbanService
from app.presentation.dependencies import get_current_user, get_kanban_service
from app.presentation.middleware.auth_middleware import CurrentUser

router = APIRouter(tags=["kanban"])

_VALID_GROUP_BY = {"state", "owner", "tag", "parent"}


@router.get("/work-items/kanban")
async def get_kanban_board(
    group_by: str = "state",
    project_id: UUID | None = None,
    limit: int = Query(default=25, ge=1, le=25),
    current_user: CurrentUser = Depends(get_current_user),
    service: KanbanService = Depends(get_kanban_service),
) -> dict[str, Any]:
    """Grouped work-items board.

    group_by=state: columns in FSM order, archived excluded.
    group_by=owner: one column per distinct owner.
    group_by=tag: one column per tag.
    group_by=parent: one column per parent work item.
    Response cached 30s per parameter combination.
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )

    if group_by not in _VALID_GROUP_BY:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_GROUP_BY",
                    "message": f"group_by must be one of: {sorted(_VALID_GROUP_BY)}",
                    "details": {},
                }
            },
        )

    try:
        data = await service.get_board(
            workspace_id=current_user.workspace_id,
            group_by=group_by,
            project_id=project_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_PARAMETER", "message": str(exc), "details": {}}},
        ) from exc

    return {"data": data, "message": "ok"}
