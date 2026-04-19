"""EP-08 Group D — Assignment controller.

Routes:
  POST /api/v1/work-items/bulk-assign            — assign multiple items at once
  GET  /api/v1/work-items/suggested-owner        — query routing-rule suggestion
  GET  /api/v1/work-items/suggested-reviewer     — query routing-rule suggestion

All routes are workspace-scoped. Target validation (suspended / non-member)
is enforced at the service layer; the controller only translates HTTP.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.events.event_bus import EventBus
from app.application.services.assignment_service import (
    AssignmentService,
    ValidationError,
)
from app.infrastructure.persistence.project_repository_impl import (
    RoutingRuleRepositoryImpl,
)
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.work_item_repository_impl import (
    WorkItemRepositoryImpl,
)
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.presentation.dependencies import get_current_user, get_scoped_session
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["assignment"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _get_assignment_service(session: AsyncSession) -> AssignmentService:
    return AssignmentService(
        user_repo=UserRepositoryImpl(session),
        work_item_repo=WorkItemRepositoryImpl(session),
        routing_rule_repo=RoutingRuleRepositoryImpl(session),
        membership_repo=WorkspaceMembershipRepositoryImpl(session),
        event_bus=EventBus(),
    )


# ---------------------------------------------------------------------------
# POST /work-items/bulk-assign
# ---------------------------------------------------------------------------


class BulkAssignBody(BaseModel):
    item_ids: list[UUID] = Field(..., min_length=1, max_length=100)
    user_id: UUID


@router.post("/work-items/bulk-assign", status_code=http_status.HTTP_200_OK)
async def bulk_assign(
    body: BulkAssignBody,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    """Assign a single owner to multiple work items in one request.

    Returns per-item results `[{item_id, success, error?}, ...]`.
    Suspended target → 422 (all-or-nothing, none assigned).
    """
    svc = _get_assignment_service(session)
    try:
        results = await svc.bulk_assign(
            item_ids=body.item_ids,
            user_id=body.user_id,
            actor_id=current_user.id,
            workspace_id=current_user.workspace_id,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "ASSIGNMENT_TARGET_INVALID",
                    "message": str(exc),
                    "details": {"user_id": str(body.user_id)},
                }
            },
        ) from exc
    return _ok(results, "bulk assignment complete")


# ---------------------------------------------------------------------------
# GET /work-items/suggested-owner
# ---------------------------------------------------------------------------


@router.get("/work-items/suggested-owner")
async def suggested_owner(
    item_type: str = Query(..., description="Work item type to look up"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    """Return the routing-rule suggested owner for a given item type.

    Returns `data: null` when no rule matches or every candidate is suspended.
    """
    svc = _get_assignment_service(session)
    suggestion = await svc.suggest_owner(
        item_type=item_type,
        workspace_id=current_user.workspace_id,
    )
    return _ok(suggestion, "ok" if suggestion else "no suggestion")


# ---------------------------------------------------------------------------
# GET /work-items/suggested-reviewer
# ---------------------------------------------------------------------------


@router.get("/work-items/suggested-reviewer")
async def suggested_reviewer(
    item_type: str = Query(..., description="Work item type to look up"),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    """Return the routing-rule suggested reviewer (team or user) for a given item type.

    Returns `data: null` when no rule matches or every candidate is suspended.
    """
    svc = _get_assignment_service(session)
    suggestion = await svc.suggest_reviewer(
        item_type=item_type,
        workspace_id=current_user.workspace_id,
    )
    return _ok(suggestion, "ok" if suggestion else "no suggestion")
