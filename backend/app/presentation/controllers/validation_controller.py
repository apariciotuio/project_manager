"""EP-06 — Validation checklist controller.

Routes:
  GET  /api/v1/work-items/{id}/validations             — checklist
  POST /api/v1/work-items/{id}/validations/{rule_id}/waive — waive recommended rule
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status

from app.application.services.review_request_service import ValidationRuleNotFoundError
from app.application.services.validation_service import ValidationService
from app.domain.models.review import (
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
    WaiveRequiredRuleError,
)
from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
from app.presentation.dependencies import (
    get_current_user,
    get_validation_service,
    get_work_item_repo_scoped,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validations"])


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _rule_status_payload(
    rule: ValidationRequirement,
    status: ValidationStatus | None,
) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "label": rule.label,
        "required": rule.required,
        "status": status.status.value if status else ValidationState.PENDING.value,
        "passed_at": status.passed_at.isoformat() if status and status.passed_at else None,
        "passed_by_review_request_id": (
            str(status.passed_by_review_request_id)
            if status and status.passed_by_review_request_id
            else None
        ),
        "waived_at": status.waived_at.isoformat() if status and status.waived_at else None,
        "waived_by": str(status.waived_by) if status and status.waived_by else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/work-items/{work_item_id}/validations")
async def get_validations(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ValidationService = Depends(get_validation_service),
    work_item_repo: WorkItemRepositoryImpl = Depends(get_work_item_repo_scoped),
) -> dict[str, Any]:
    _require_workspace(current_user)
    workspace_id = current_user.workspace_id  # narrowed: _require_workspace guarantees non-None
    assert workspace_id is not None  # type narrowing for mypy
    work_item = await work_item_repo.get(work_item_id, workspace_id)
    work_item_type = work_item.type.value if work_item is not None else ""
    result = await service.get_checklist(
        work_item_id=work_item_id,
        workspace_id=workspace_id,
        work_item_type=work_item_type,
    )
    return _ok(
        {
            "required": [_rule_status_payload(r, s) for r, s in result.required],
            "recommended": [_rule_status_payload(r, s) for r, s in result.recommended],
        }
    )


@router.post(
    "/work-items/{work_item_id}/validations/{rule_id}/waive",
    status_code=http_status.HTTP_200_OK,
)
async def waive_validation(
    work_item_id: UUID,
    rule_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: ValidationService = Depends(get_validation_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        vs = await service.waive_validation(
            work_item_id=work_item_id,
            rule_id=rule_id,
            workspace_id=current_user.workspace_id,  # type: ignore[arg-type]
            waived_by=current_user.id,
        )
    except WaiveRequiredRuleError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "CANNOT_WAIVE_REQUIRED", "message": str(exc), "details": {}}},
        ) from exc
    except ValidationRuleNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(
        {
            "rule_id": vs.rule_id,
            "status": vs.status.value,
            "waived_at": vs.waived_at.isoformat() if vs.waived_at else None,
            "waived_by": str(vs.waived_by) if vs.waived_by else None,
        },
        "validation waived",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_workspace(user: CurrentUser) -> None:
    if user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
