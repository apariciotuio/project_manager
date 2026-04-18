"""EP-04 Phase 6 — NextStep controller.

Route:
  GET /api/v1/work-items/{id}/next-step — next action + suggested validators
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.next_step_service import NextStepService
from app.presentation.dependencies import get_current_user, get_next_step_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["next-step"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/work-items/{work_item_id}/next-step")
async def get_next_step(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: NextStepService = Depends(get_next_step_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    workspace_id = current_user.workspace_id
    try:
        result = await service.recommend(work_item_id, workspace_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(
        {
            "next_step": result.next_step,
            "message": result.message,
            "blocking": result.blocking,
            "gaps_referenced": result.gaps_referenced,
            "suggested_validators": result.suggested_validators,
        }
    )
