"""EP-10 — Admin validation rules controller.

Routes:
  GET    /api/v1/admin/rules/validation
  POST   /api/v1/admin/rules/validation
  PATCH  /api/v1/admin/rules/validation/{id}
  DELETE /api/v1/admin/rules/validation/{id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import AuditService
from app.application.services.validation_rule_service import (
    DuplicateRuleError,
    GlobalBlockerInEffectError,
    RuleHasHistoryError,
    ValidationRuleNotFoundError,
    ValidationRuleService,
)
from app.infrastructure.persistence.validation_rule_repository_impl import (
    ValidationRuleRepositoryImpl,
)
from app.presentation.dependencies import get_audit_service, get_db_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rules", tags=["admin-rules"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _rule_payload(r: Any) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "workspace_id": str(r.workspace_id),
        "project_id": str(r.project_id) if r.project_id else None,
        "work_item_type": r.work_item_type,
        "validation_type": r.validation_type,
        "enforcement": r.enforcement,
        "active": r.active,
        "effective": getattr(r, "effective", True),
        "superseded_by": str(r.superseded_by) if getattr(r, "superseded_by", None) else None,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


def get_validation_rule_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> ValidationRuleService:
    return ValidationRuleService(
        repo=ValidationRuleRepositoryImpl(session),
        audit=audit,
    )


@router.get("/validation")
async def list_validation_rules(
    project_id: UUID | None = Query(default=None),
    work_item_type: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleService = Depends(get_validation_rule_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    rules = await service.list_rules(
        current_user.workspace_id,
        project_id=project_id,
        work_item_type=work_item_type,
    )
    return _ok([_rule_payload(r) for r in rules])


class CreateValidationRuleRequest(BaseModel):
    project_id: UUID | None = None
    work_item_type: str
    validation_type: str
    enforcement: str = "recommended"


@router.post("/validation", status_code=http_status.HTTP_201_CREATED)
async def create_validation_rule(
    body: CreateValidationRuleRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleService = Depends(get_validation_rule_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        rule = await service.create_rule(
            current_user.workspace_id,
            project_id=body.project_id,
            work_item_type=body.work_item_type,
            validation_type=body.validation_type,
            enforcement=body.enforcement,
            actor_id=current_user.id,
        )
    except GlobalBlockerInEffectError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "global_blocker_in_effect", "message": str(exc), "details": {}}},
        ) from exc
    except DuplicateRuleError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "rule_already_exists",
                    "message": str(exc),
                    "details": {"existing_id": str(exc.existing_id)},
                }
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_rule_payload(rule), "validation rule created")


class PatchValidationRuleRequest(BaseModel):
    enforcement: str | None = None
    active: bool | None = None


@router.patch("/validation/{rule_id}")
async def update_validation_rule(
    rule_id: UUID,
    body: PatchValidationRuleRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleService = Depends(get_validation_rule_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        updated, superseded_ids = await service.update_rule(
            current_user.workspace_id,
            rule_id,
            enforcement=body.enforcement,
            active=body.active,
            actor_id=current_user.id,
        )
    except ValidationRuleNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc

    payload = _rule_payload(updated)
    warnings = [f"superseded rule {rid}" for rid in superseded_ids]
    return _ok({**payload, "warnings": warnings}, "validation rule updated")


@router.delete("/validation/{rule_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_validation_rule(
    rule_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleService = Depends(get_validation_rule_service),
) -> None:
    assert current_user.workspace_id is not None
    try:
        await service.delete_rule(
            current_user.workspace_id, rule_id, current_user.id
        )
    except ValidationRuleNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except RuleHasHistoryError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "rule_has_history", "message": str(exc), "details": {}}},
        ) from exc
