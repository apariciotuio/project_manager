"""EP-10 — RoutingRule admin REST controller.

Routes:
  GET    /api/v1/routing-rules
  POST   /api/v1/routing-rules
  GET    /api/v1/routing-rules/{rule_id}
  PATCH  /api/v1/routing-rules/{rule_id}
  DELETE /api/v1/routing-rules/{rule_id}

All endpoints require admin role (workspace admin or superadmin).
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.project_service import (
    ProjectService,
    RoutingRuleNotFoundError,
)
from app.presentation.dependencies import (
    get_project_service,
    require_admin,
)
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["routing-rules"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _rule_payload(r: Any) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "workspace_id": str(r.workspace_id),
        "project_id": str(r.project_id) if r.project_id else None,
        "work_item_type": r.work_item_type,
        "suggested_team_id": str(r.suggested_team_id) if r.suggested_team_id else None,
        "suggested_owner_id": str(r.suggested_owner_id) if r.suggested_owner_id else None,
        "suggested_validators": r.suggested_validators,
        "priority": r.priority,
        "active": r.active,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
        "created_by": str(r.created_by),
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": "routing rule not found", "details": {}}},
    )


class CreateRoutingRuleRequest(BaseModel):
    work_item_type: str
    project_id: UUID | None = None
    suggested_team_id: UUID | None = None
    suggested_owner_id: UUID | None = None
    suggested_validators: list[str] = []
    priority: int = 0


class PatchRoutingRuleRequest(BaseModel):
    suggested_team_id: UUID | None = None
    suggested_owner_id: UUID | None = None
    suggested_validators: list[str] | None = None
    priority: int | None = None
    active: bool | None = None


@router.get("/routing-rules")
async def list_routing_rules(
    current_user: CurrentUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    # require_admin raises 401 when workspace_id is None — workspace_id is guaranteed here
    assert current_user.workspace_id is not None
    rules = await service.list_routing_rules(current_user.workspace_id)
    return _ok([_rule_payload(r) for r in rules])


@router.post("/routing-rules", status_code=http_status.HTTP_201_CREATED)
async def create_routing_rule(
    body: CreateRoutingRuleRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    rule = await service.create_routing_rule(
        workspace_id=current_user.workspace_id,
        work_item_type=body.work_item_type,
        created_by=current_user.id,
        project_id=body.project_id,
        suggested_team_id=body.suggested_team_id,
        suggested_owner_id=body.suggested_owner_id,
        suggested_validators=body.suggested_validators,
        priority=body.priority,
    )
    return _ok(_rule_payload(rule), "routing rule created")


@router.get("/routing-rules/{rule_id}")
async def get_routing_rule(
    rule_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        rule = await service.get_routing_rule(
            rule_id, workspace_id=current_user.workspace_id
        )
    except RoutingRuleNotFoundError as exc:
        raise _not_found() from exc
    return _ok(_rule_payload(rule))


@router.patch("/routing-rules/{rule_id}")
async def patch_routing_rule(
    rule_id: UUID,
    body: PatchRoutingRuleRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        rule = await service.update_routing_rule(
            rule_id,
            workspace_id=current_user.workspace_id,
            suggested_team_id=body.suggested_team_id,
            suggested_owner_id=body.suggested_owner_id,
            suggested_validators=body.suggested_validators,
            priority=body.priority,
            active=body.active,
        )
    except RoutingRuleNotFoundError as exc:
        raise _not_found() from exc
    return _ok(_rule_payload(rule), "routing rule updated")


@router.delete("/routing-rules/{rule_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_routing_rule(
    rule_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: ProjectService = Depends(get_project_service),
) -> None:
    assert current_user.workspace_id is not None
    try:
        await service.delete_routing_rule(
            rule_id, workspace_id=current_user.workspace_id
        )
    except RoutingRuleNotFoundError as exc:
        raise _not_found() from exc
