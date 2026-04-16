"""EP-04 Phase 8 — Specification controller.

Routes:
  GET  /api/v1/work-items/{id}/specification              — list sections
  PATCH /api/v1/work-items/{id}/sections/{section_id}     — update single section
  GET  /api/v1/work-items/{id}/sections/{section_id}/versions — section history

Deferred (needs Dundun agent plumbing or EP-07):
  POST /api/v1/work-items/{id}/specification/generate
  PATCH /api/v1/work-items/{id}/sections                  — bulk update
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.section_service import (
    SectionForbiddenError,
    SectionNotFoundError,
    SectionService,
)
from app.domain.models.section import RequiredSectionEmptyError
from app.presentation.dependencies import get_current_user, get_section_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["specification"])


class UpdateSectionRequest(BaseModel):
    content: str


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _section_payload(section: Any) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "work_item_id": str(section.work_item_id),
        "section_type": section.section_type.value,
        "content": section.content,
        "display_order": section.display_order,
        "is_required": section.is_required,
        "generation_source": section.generation_source.value,
        "version": section.version,
        "created_at": section.created_at.isoformat(),
        "updated_at": section.updated_at.isoformat(),
        "created_by": str(section.created_by),
        "updated_by": str(section.updated_by),
    }


@router.get("/work-items/{work_item_id}/specification")
async def get_specification(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: SectionService = Depends(get_section_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}
            },
        )
    try:
        sections = await service.list_for_work_item(
            work_item_id, current_user.workspace_id
        )
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "work item not found", "details": {}}},
        ) from exc
    return _ok(
        {
            "work_item_id": str(work_item_id),
            "sections": [_section_payload(s) for s in sections],
        }
    )


@router.patch("/work-items/{work_item_id}/sections/{section_id}")
async def update_section(
    work_item_id: UUID,
    section_id: UUID,
    body: UpdateSectionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SectionService = Depends(get_section_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}
            },
        )
    try:
        section = await service.update_section(
            section_id=section_id,
            work_item_id=work_item_id,
            workspace_id=current_user.workspace_id,
            actor_id=current_user.id,
            new_content=body.content,
        )
    except SectionNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except SectionForbiddenError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "SPEC_EDIT_FORBIDDEN",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc
    except RequiredSectionEmptyError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "REQUIRED_SECTION_EMPTY",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc
    return _ok(_section_payload(section))
