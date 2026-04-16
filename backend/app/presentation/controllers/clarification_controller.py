"""EP-03 Phase 7 — Clarification controller (rules-based only).

Routes:
  GET /api/v1/work-items/{id}/gaps/questions — top 3 blocking questions

Deferred (owned by EP-04):
  POST /api/v1/work-items/{id}/gaps/ai-review — AI review dispatch
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi import status as http_status  # noqa: F401

from app.application.services.clarification_service import ClarificationService
from app.presentation.dependencies import get_clarification_service, get_current_user
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clarification"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.get("/work-items/{work_item_id}/gaps/questions")
async def get_gap_questions(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ClarificationService = Depends(get_clarification_service),
) -> dict[str, Any]:
    """Return up to 3 blocking gap questions for the given work item.

    WorkItemNotFoundError bubbles to error middleware → 404.
    """
    if current_user.workspace_id is None:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )

    questions = await service.get_next_questions(work_item_id, current_user.workspace_id)
    return _ok({"questions": questions})
