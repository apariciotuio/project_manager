"""EP-02 — Template controller.

Routes:
  GET    /templates              — get template for workspace+type
  POST   /templates              — create workspace template (admin only)
  PATCH  /templates/{id}         — update template (admin only)
  DELETE /templates/{id}         — delete template (admin only)
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.application.services.template_service import TemplateService
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.presentation.dependencies import (
    get_current_user,
    get_membership_repo_scoped,
    get_template_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.schemas.template_schemas import (
    CreateTemplateRequest,
    TemplateResponse,
    UpdateTemplateRequest,
)

router = APIRouter(tags=["templates"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


async def _resolve_role(
    membership_repo: WorkspaceMembershipRepositoryImpl,
    user_id: UUID,
    workspace_id: UUID,
) -> str:
    membership = await membership_repo.get_for_user_and_workspace(user_id, workspace_id)
    return membership.role if membership else "member"


@router.get("/templates")
async def get_template(
    type: WorkItemType,
    workspace_id: UUID = Query(...),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth trigger
    service: TemplateService = Depends(get_template_service),
) -> dict[str, Any]:
    tmpl = await service.get_template_for_type(type, workspace_id)
    if tmpl is None:
        return _ok(None)
    return _ok(TemplateResponse.from_domain(tmpl).model_dump(mode="json"))


@router.post("/templates", status_code=status.HTTP_201_CREATED)
async def create_template(
    body: CreateTemplateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    membership_repo: WorkspaceMembershipRepositoryImpl = Depends(get_membership_repo_scoped),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    role = await _resolve_role(membership_repo, current_user.id, current_user.workspace_id)

    result = await service.create_template(
        workspace_id=current_user.workspace_id,
        type=body.type,
        name=body.name,
        content=body.content,
        actor_id=current_user.id,
        actor_role=role,
    )
    return _ok(TemplateResponse.from_domain(result).model_dump(mode="json"))


@router.patch("/templates/{template_id}")
async def update_template(
    template_id: UUID,
    body: UpdateTemplateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    membership_repo: WorkspaceMembershipRepositoryImpl = Depends(get_membership_repo_scoped),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    role = await _resolve_role(membership_repo, current_user.id, current_user.workspace_id)

    result = await service.update_template(
        template_id=template_id,
        name=body.name,
        content=body.content,
        actor_id=current_user.id,
        actor_role=role,
    )
    return _ok(TemplateResponse.from_domain(result).model_dump(mode="json"))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TemplateService = Depends(get_template_service),
    membership_repo: WorkspaceMembershipRepositoryImpl = Depends(get_membership_repo_scoped),
) -> Response:
    assert current_user.workspace_id is not None
    role = await _resolve_role(membership_repo, current_user.id, current_user.workspace_id)

    await service.delete_template(
        template_id=template_id,
        actor_id=current_user.id,
        actor_role=role,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
