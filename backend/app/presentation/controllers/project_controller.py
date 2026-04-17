"""EP-10 — Project controller.

Routes:
  POST   /api/v1/projects
  GET    /api/v1/projects
  GET    /api/v1/projects/{project_id}
  PATCH  /api/v1/projects/{project_id}
  DELETE /api/v1/projects/{project_id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.application.services.project_service import (
    ProjectNotFoundError,
    ProjectService,
)
from app.presentation.dependencies import get_current_user, get_project_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["projects"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _project_payload(p: Any) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "workspace_id": str(p.workspace_id),
        "name": p.name,
        "description": p.description,
        "deleted_at": p.deleted_at.isoformat() if p.deleted_at else None,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "created_by": str(p.created_by),
    }


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


@router.post("/projects", status_code=http_status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        project = await service.create(
            workspace_id=current_user.workspace_id,
            name=body.name,
            created_by=current_user.id,
            description=body.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "PROJECT_NAME_TAKEN",
                    "message": f"project name '{body.name}' already exists in this workspace",
                    "details": {},
                }
            },
        ) from exc
    return _ok(_project_payload(project), "project created")


@router.get("/projects")
async def list_projects(
    current_user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    projects = await service.list_for_workspace(current_user.workspace_id)
    return _ok([_project_payload(p) for p in projects])


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        project = await service.get(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_project_payload(project))


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    body: UpdateProjectRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        project = await service.update(
            project_id, name=body.name, description=body.description
        )
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_project_payload(project))


@router.delete("/projects/{project_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> None:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        await service.soft_delete(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
