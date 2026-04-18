"""EP-10 — Admin context presets controller.

Routes:
  GET    /api/v1/admin/context-presets
  POST   /api/v1/admin/context-presets
  GET    /api/v1/admin/context-presets/{id}
  PATCH  /api/v1/admin/context-presets/{id}
  DELETE /api/v1/admin/context-presets/{id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import AuditService
from app.application.services.context_preset_service import (
    ContextPresetNotFoundError,
    ContextPresetService,
    DuplicatePresetNameError,
    PresetInUseError,
)
from app.infrastructure.persistence.context_preset_repository_impl import (
    ContextPresetRepositoryImpl,
)
from app.presentation.dependencies import get_audit_service, get_db_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/context-presets", tags=["admin-context-presets"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _preset_payload(p: Any) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "workspace_id": str(p.workspace_id),
        "name": p.name,
        "description": p.description,
        "sources": [s.to_dict() for s in p.sources],
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }


def get_context_preset_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> ContextPresetService:
    return ContextPresetService(
        repo=ContextPresetRepositoryImpl(session),
        audit=audit,
        session=session,
    )


@router.get("")
async def list_presets(
    current_user: CurrentUser = Depends(require_admin),
    service: ContextPresetService = Depends(get_context_preset_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    presets = await service.list_presets(current_user.workspace_id)
    return _ok([_preset_payload(p) for p in presets])


class CreatePresetRequest(BaseModel):
    name: str
    description: str | None = None
    sources: list[dict] = []


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def create_preset(
    body: CreatePresetRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ContextPresetService = Depends(get_context_preset_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        preset = await service.create_preset(
            current_user.workspace_id,
            name=body.name,
            description=body.description,
            sources=body.sources,
            actor_id=current_user.id,
        )
    except DuplicatePresetNameError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "duplicate_preset_name", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_preset_payload(preset), "context preset created")


@router.get("/{preset_id}")
async def get_preset(
    preset_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ContextPresetService = Depends(get_context_preset_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        preset = await service.get_preset(current_user.workspace_id, preset_id)
    except ContextPresetNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_preset_payload(preset))


class PatchPresetRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    sources: list[dict] | None = None


@router.patch("/{preset_id}")
async def update_preset(
    preset_id: UUID,
    body: PatchPresetRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ContextPresetService = Depends(get_context_preset_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        updated = await service.update_preset(
            current_user.workspace_id,
            preset_id,
            name=body.name,
            description=body.description,
            sources=body.sources,
            actor_id=current_user.id,
        )
    except ContextPresetNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except DuplicatePresetNameError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "duplicate_preset_name", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_preset_payload(updated), "context preset updated")


@router.delete("/{preset_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ContextPresetService = Depends(get_context_preset_service),
) -> None:
    assert current_user.workspace_id is not None
    try:
        await service.delete_preset(
            current_user.workspace_id, preset_id, current_user.id
        )
    except ContextPresetNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except PresetInUseError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "preset_in_use", "message": str(exc), "details": {}}},
        ) from exc
