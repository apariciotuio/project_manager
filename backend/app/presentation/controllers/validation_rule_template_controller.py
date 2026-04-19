"""EP-10 — ValidationRuleTemplate admin REST controller.

Routes:
  GET    /api/v1/validation-rule-templates
  POST   /api/v1/validation-rule-templates
  GET    /api/v1/validation-rule-templates/{template_id}
  PATCH  /api/v1/validation-rule-templates/{template_id}
  DELETE /api/v1/validation-rule-templates/{template_id}

All endpoints require admin role (workspace admin or superadmin).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.validation_rule_template_service import (
    ValidationRuleTemplateNotFoundError,
    ValidationRuleTemplateService,
)
from app.presentation.dependencies import (
    get_validation_rule_template_service,
    require_admin,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["validation-rule-templates"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _template_payload(t: Any) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "workspace_id": str(t.workspace_id) if t.workspace_id else None,
        "name": t.name,
        "work_item_type": t.work_item_type,
        "requirement_type": t.requirement_type,
        "default_dimension": t.default_dimension,
        "default_description": t.default_description,
        "is_mandatory": t.is_mandatory,
        "active": t.active,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail={
            "error": {
                "code": "NOT_FOUND",
                "message": "validation rule template not found",
                "details": {},
            }
        },
    )


class CreateVRTRequest(BaseModel):
    name: str
    requirement_type: str
    is_mandatory: bool
    work_item_type: str | None = None
    default_dimension: str | None = None
    default_description: str | None = None


class PatchVRTRequest(BaseModel):
    name: str | None = None
    is_mandatory: bool | None = None
    default_dimension: str | None = None
    default_description: str | None = None
    active: bool | None = None


@router.get("/validation-rule-templates")
async def list_validation_rule_templates(
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleTemplateService = Depends(get_validation_rule_template_service),
) -> dict[str, Any]:
    # require_admin raises 401 when workspace_id is None — workspace_id is guaranteed here
    assert current_user.workspace_id is not None
    templates = await service.list_for_workspace(current_user.workspace_id)
    return _ok([_template_payload(t) for t in templates])


@router.post("/validation-rule-templates", status_code=http_status.HTTP_201_CREATED)
async def create_validation_rule_template(
    body: CreateVRTRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleTemplateService = Depends(get_validation_rule_template_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        template = await service.create(
            name=body.name,
            requirement_type=body.requirement_type,
            is_mandatory=body.is_mandatory,
            workspace_id=current_user.workspace_id,
            work_item_type=body.work_item_type,
            default_dimension=body.default_dimension,
            default_description=body.default_description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_template_payload(template), "validation rule template created")


@router.get("/validation-rule-templates/{template_id}")
async def get_validation_rule_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleTemplateService = Depends(get_validation_rule_template_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        template = await service.get(
            template_id, workspace_id=current_user.workspace_id
        )
    except ValidationRuleTemplateNotFoundError as exc:
        raise _not_found() from exc
    return _ok(_template_payload(template))


@router.patch("/validation-rule-templates/{template_id}")
async def patch_validation_rule_template(
    template_id: UUID,
    body: PatchVRTRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleTemplateService = Depends(get_validation_rule_template_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        template = await service.update(
            template_id,
            workspace_id=current_user.workspace_id,
            name=body.name,
            is_mandatory=body.is_mandatory,
            default_dimension=body.default_dimension,
            default_description=body.default_description,
            active=body.active,
        )
    except ValidationRuleTemplateNotFoundError as exc:
        raise _not_found() from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_template_payload(template), "validation rule template updated")


@router.delete(
    "/validation-rule-templates/{template_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def delete_validation_rule_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ValidationRuleTemplateService = Depends(get_validation_rule_template_service),
) -> None:
    assert current_user.workspace_id is not None
    try:
        await service.delete(template_id, workspace_id=current_user.workspace_id)
    except ValidationRuleTemplateNotFoundError as exc:
        raise _not_found() from exc
