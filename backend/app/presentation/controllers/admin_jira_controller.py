"""EP-10 — Admin Jira integration controller.

Routes:
  GET    /api/v1/admin/integrations/jira
  POST   /api/v1/admin/integrations/jira
  GET    /api/v1/admin/integrations/jira/{id}
  PATCH  /api/v1/admin/integrations/jira/{id}
  POST   /api/v1/admin/integrations/jira/{id}/test
  GET    /api/v1/admin/integrations/jira/{id}/mappings
  POST   /api/v1/admin/integrations/jira/{id}/mappings

NEVER return credentials_ref in any response.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import AuditService
from app.application.services.jira_config_service import (
    InvalidBaseUrlError,
    JiraConfigDisabledError,
    JiraConfigExistsError,
    JiraConfigNotFoundError,
    JiraConfigService,
)
from app.infrastructure.persistence.jira_config_repository_impl import (
    JiraConfigRepositoryImpl,
)
from app.presentation.dependencies import get_audit_service, get_db_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/integrations/jira", tags=["admin-jira"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _config_payload(c: Any) -> dict[str, Any]:
    """NEVER include credentials_ref."""
    return {
        "id": str(c.id),
        "workspace_id": str(c.workspace_id),
        "project_id": str(c.project_id) if c.project_id else None,
        "base_url": c.base_url,
        "auth_type": c.auth_type,
        "state": c.state,
        "last_health_check_status": c.last_health_check_status,
        "last_health_check_at": c.last_health_check_at.isoformat() if c.last_health_check_at else None,
        "created_at": c.created_at.isoformat(),
    }


def _mapping_payload(m: Any) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "jira_config_id": str(m.jira_config_id),
        "jira_project_key": m.jira_project_key,
        "local_project_id": str(m.local_project_id) if m.local_project_id else None,
        "type_mappings": m.type_mappings,
    }


def get_jira_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> JiraConfigService:
    return JiraConfigService(
        repo=JiraConfigRepositoryImpl(session),
        audit=audit,
    )


@router.get("")
async def list_jira_configs(
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    configs = await service.list_configs(current_user.workspace_id)
    return _ok([_config_payload(c) for c in configs])


class CreateJiraConfigRequest(BaseModel):
    base_url: str
    auth_type: str = "basic"
    credentials: dict[str, str]
    project_id: UUID | None = None

    @field_validator("base_url")
    @classmethod
    def validate_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("base_url must use HTTPS")
        return v.rstrip("/")


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def create_jira_config(
    body: CreateJiraConfigRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    # credentials_ref is the raw encrypted value — in production this would
    # go through CredentialsStore.encrypt(). For now store the token directly.
    credentials_ref = body.credentials.get("token", "")
    try:
        config = await service.create_config(
            current_user.workspace_id,
            base_url=body.base_url,
            auth_type=body.auth_type,
            credentials_ref=credentials_ref,
            actor_id=current_user.id,
            project_id=body.project_id,
        )
    except InvalidBaseUrlError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "invalid_base_url", "message": str(exc), "details": {}}},
        ) from exc
    except JiraConfigExistsError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "jira_config_exists", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({"id": str(config.id), "state": config.state}, "jira config created")


@router.get("/{config_id}")
async def get_jira_config(
    config_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        config = await service.get_config(current_user.workspace_id, config_id)
    except JiraConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_config_payload(config))


class PatchJiraConfigRequest(BaseModel):
    credentials: dict[str, str] | None = None
    state: str | None = None


@router.patch("/{config_id}")
async def update_jira_config(
    config_id: UUID,
    body: PatchJiraConfigRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    credentials_ref: str | None = None
    if body.credentials is not None:
        credentials_ref = body.credentials.get("token")
    try:
        updated = await service.update_config(
            current_user.workspace_id,
            config_id,
            credentials_ref=credentials_ref,
            state=body.state,
            actor_id=current_user.id,
        )
    except JiraConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_config_payload(updated), "jira config updated")


@router.post("/{config_id}/test")
async def test_jira_connection(
    config_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    """Always returns 200; result in body."""
    assert current_user.workspace_id is not None
    try:
        result = await service.test_connection(current_user.workspace_id, config_id)
    except JiraConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except JiraConfigDisabledError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "config_disabled", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(result)


@router.get("/{config_id}/mappings")
async def list_jira_mappings(
    config_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        mappings = await service.list_mappings(current_user.workspace_id, config_id)
    except JiraConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok([_mapping_payload(m) for m in mappings])


class CreateMappingRequest(BaseModel):
    jira_project_key: str
    local_project_id: UUID | None = None
    type_mappings: dict | None = None


@router.post("/{config_id}/mappings", status_code=http_status.HTTP_201_CREATED)
async def create_jira_mapping(
    config_id: UUID,
    body: CreateMappingRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: JiraConfigService = Depends(get_jira_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        mapping = await service.create_mapping(
            current_user.workspace_id,
            config_id,
            jira_project_key=body.jira_project_key,
            local_project_id=body.local_project_id,
            type_mappings=body.type_mappings,
            actor_id=current_user.id,
        )
    except JiraConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_mapping_payload(mapping), "mapping created")
