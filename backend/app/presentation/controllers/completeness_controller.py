"""EP-04 Phase 8 — Completeness + Gaps controller.

Routes:
  GET /api/v1/work-items/{id}/completeness — score + dimension breakdown
  GET /api/v1/work-items/{id}/gaps         — list of unfilled dimensions
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.completeness_service import (
    CompletenessService,
    GapService,
)
from app.presentation.dependencies import (
    get_completeness_service,
    get_current_user,
    get_gap_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["completeness"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _require_workspace(current_user: CurrentUser) -> UUID:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    return current_user.workspace_id


@router.get("/work-items/{work_item_id}/completeness")
async def get_completeness(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CompletenessService = Depends(get_completeness_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    try:
        result = await service.compute(work_item_id, workspace_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(
        {
            "score": result.score,
            "level": result.level,
            "dimensions": [asdict(d) for d in result.dimensions],
            "cached": result.cached,
        }
    )


@router.get("/work-items/{work_item_id}/gaps")
async def get_gaps(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: GapService = Depends(get_gap_service),
) -> dict[str, Any]:
    workspace_id = _require_workspace(current_user)
    try:
        gaps = await service.list(work_item_id, workspace_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(gaps)
