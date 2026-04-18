"""EP-11 — Integration controller.

Routes:
  POST /api/v1/integrations/configs
  GET  /api/v1/integrations/configs
  POST /api/v1/work-items/{work_item_id}/export
  GET  /api/v1/work-items/{work_item_id}/exports
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.audit_service import AuditService
from app.application.services.export_service import (
    ExportError,
    ExportService,
    WorkItemNotFoundError,
)
from app.application.services.integration_service import (
    IntegrationConfigNotFoundError,
    IntegrationService,
)
from app.presentation.dependencies import (
    get_audit_service,
    get_current_user,
    get_export_service,
    get_integration_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["integrations"])


def _credential_fingerprint(secret: str) -> str:
    """Return the first 8 hex chars of SHA-256(secret). NEVER log the full secret."""
    return hashlib.sha256(secret.encode()).hexdigest()[:8]


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _config_payload(c: Any) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "workspace_id": str(c.workspace_id),
        "project_id": str(c.project_id) if c.project_id else None,
        "integration_type": c.integration_type,
        "mapping": c.mapping,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
        "created_by": str(c.created_by),
    }


def _export_payload(e: Any) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "integration_config_id": str(e.integration_config_id),
        "work_item_id": str(e.work_item_id),
        "external_key": e.external_key,
        "external_url": e.external_url,
        "direction": e.direction,
        "status": e.status,
        "error_message": e.error_message,
        "exported_at": e.exported_at.isoformat(),
        "exported_by": str(e.exported_by),
    }


class CreateIntegrationConfigRequest(BaseModel):
    integration_type: str
    encrypted_credentials: str
    project_id: UUID | None = None
    mapping: dict[str, Any] | None = None


class TriggerExportRequest(BaseModel):
    integration_config_id: UUID
    snapshot: dict[str, Any] | None = None


@router.post("/integrations/configs", status_code=http_status.HTTP_201_CREATED)
async def create_integration_config(
    request: Request,
    body: CreateIntegrationConfigRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    config = await service.create_config(
        workspace_id=current_user.workspace_id,
        integration_type=body.integration_type,
        encrypted_credentials=body.encrypted_credentials,
        created_by=current_user.id,
        project_id=body.project_id,
        mapping=body.mapping,
    )
    try:
        await audit.log_event(
            category="admin",
            action="credential_create",
            actor_id=current_user.id,
            workspace_id=current_user.workspace_id,
            entity_type="integration_config",
            entity_id=config.id,
            context={
                "outcome": "success",
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "integration_type": body.integration_type,
                "credential_fingerprint": _credential_fingerprint(body.encrypted_credentials),
            },
        )
    except Exception:
        logger.exception("audit log failed for credential_create")
    return _ok(_config_payload(config), "integration config created")


@router.get("/integrations/configs")
async def list_integration_configs(
    current_user: CurrentUser = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    configs = await service.list_active_configs(current_user.workspace_id)
    return _ok([_config_payload(c) for c in configs])


@router.post(
    "/work-items/{work_item_id}/export",
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def trigger_export(
    work_item_id: UUID,
    body: TriggerExportRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        export = await service.trigger_export(
            work_item_id=work_item_id,
            workspace_id=current_user.workspace_id,
            integration_config_id=body.integration_config_id,
            snapshot=body.snapshot or {},
            exported_by=current_user.id,
        )
    except IntegrationConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_export_payload(export), "export queued")


@router.get("/work-items/{work_item_id}/exports")
async def list_exports(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    exports = await service.list_exports(work_item_id)
    return _ok([_export_payload(e) for e in exports])


class ExportToJiraRequest(BaseModel):
    project_key: str


@router.post(
    "/work-items/{work_item_id}/export/jira",
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def export_to_jira(
    work_item_id: UUID,
    body: ExportToJiraRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    service: ExportService = Depends(get_export_service),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    """POST /api/v1/work-items/{id}/export/jira — authenticated + workspace-scoped.

    Enqueues the Jira export as a BackgroundTask. Returns 202 immediately.

    TODO(pg-jobs): crash mid-export = silent failure; promote to pg-jobs if
    reliability needed.
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )

    job_id = str(work_item_id)

    # Emit queued audit immediately — before background task runs.
    try:
        await audit.log_event(
            category="domain",
            action="jira_export_queued",
            actor_id=current_user.id,
            workspace_id=current_user.workspace_id,
            entity_type="work_item",
            entity_id=work_item_id,
            context={
                "outcome": "success",
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
    except Exception:
        logger.exception("audit log failed for jira_export_queued")

    background_tasks.add_task(
        _run_export,
        service=service,
        audit=audit,
        work_item_id=work_item_id,
        workspace_id=current_user.workspace_id,
        user_id=current_user.id,
        project_key=body.project_key,
    )

    return _ok({"job_id": job_id, "status": "queued"}, "export queued")


async def _run_export(
    *,
    service: ExportService,
    audit: AuditService,
    work_item_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
    project_key: str,
) -> None:
    """Background task wrapper — logs errors, does not raise."""
    error_code: str | None = None
    jira_key: str | None = None

    try:
        issue = await service.export_work_item_to_jira(
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            user_id=user_id,
            project_key=project_key,
        )
        jira_key = issue.key
    except WorkItemNotFoundError:
        logger.warning("export: work item %s not found in workspace %s", work_item_id, workspace_id)
        error_code = "WORK_ITEM_NOT_FOUND"
    except ExportError as exc:
        logger.error("export: jira error %s for work_item %s: %s", exc.code, work_item_id, exc)
        error_code = exc.code
    except Exception as exc:
        logger.exception("export: unexpected error for work_item %s", work_item_id)
        error_code = type(exc).__name__

    # Emit completed audit regardless of outcome.
    ctx: dict[str, object] = {"outcome": "success" if error_code is None else "failure"}
    if jira_key is not None:
        ctx["jira_key"] = jira_key
    if error_code is not None:
        ctx["error"] = error_code
    try:
        await audit.log_event(
            category="domain",
            action="jira_export_completed",
            actor_id=user_id,
            workspace_id=workspace_id,
            entity_type="work_item",
            entity_id=work_item_id,
            context=ctx,
        )
    except Exception:
        logger.exception("audit log failed for jira_export_completed")


@router.delete(
    "/integrations/configs/{config_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def delete_integration_config(
    config_id: UUID,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: IntegrationService = Depends(get_integration_service),
    audit: AuditService = Depends(get_audit_service),
) -> None:
    """Delete an integration config.

    Owner/admin only. Workspace-scoped — 404 for cross-workspace access (IDOR mitigation).
    Exported records referencing this config are NOT deleted (CASCADE is intentionally
    avoided; audit trail must be preserved).
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        await service.delete_config(config_id, workspace_id=current_user.workspace_id)
    except IntegrationConfigNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    try:
        await audit.log_event(
            category="admin",
            action="credential_delete",
            actor_id=current_user.id,
            workspace_id=current_user.workspace_id,
            entity_type="integration_config",
            entity_id=config_id,
            context={
                "outcome": "success",
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )
    except Exception:
        logger.exception("audit log failed for credential_delete")
