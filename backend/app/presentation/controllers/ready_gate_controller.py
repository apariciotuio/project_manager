"""EP-06 — ReadyGate controller.

Routes:
  GET /api/v1/work-items/{id}/ready-gate — check if item can transition to READY
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.ready_gate_service import ReadyGateService
from app.presentation.dependencies import get_current_user, get_ready_gate_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ready-gate"])


@router.get("/work-items/{work_item_id}/ready-gate")
async def check_ready_gate(
    work_item_id: UUID,
    work_item_type: str = "",
    current_user: CurrentUser = Depends(get_current_user),
    service: ReadyGateService = Depends(get_ready_gate_service),
) -> dict[str, Any]:
    """Return gate status so FE can render a checklist before attempting transition."""
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    result = await service.check(
        work_item_id=work_item_id,
        workspace_id=current_user.workspace_id,
        work_item_type=work_item_type,
    )
    return {
        "data": {
            "ok": result.ok,
            "blockers": [
                {
                    "code": b.rule_id,
                    "rule_id": b.rule_id,
                    "label": b.label,
                    "status": b.status,
                }
                for b in result.blockers
            ],
        }
    }
