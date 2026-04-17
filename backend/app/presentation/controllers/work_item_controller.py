"""EP-01 Phase 4 — Work Item controller.

Thin HTTP handlers: validate → build command → call service → envelope response.
Zero business logic here.

workspace_id is guaranteed non-None by get_scoped_session — it raises 401 before
reaching any handler if the JWT has no workspace_id claim.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import Response

from app.application.commands.create_work_item_command import CreateWorkItemCommand
from app.application.commands.delete_work_item_command import DeleteWorkItemCommand
from app.application.commands.force_ready_command import ForceReadyCommand
from app.application.commands.reassign_owner_command import ReassignOwnerCommand
from app.application.commands.transition_state_command import TransitionStateCommand
from app.application.commands.update_work_item_command import UpdateWorkItemCommand
from app.application.services.draft_service import DraftService
from app.application.services.work_item_service import WorkItemService
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.presentation.dependencies import (
    get_current_user,
    get_draft_service,
    get_work_item_service,
)
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.schemas.draft_schemas import SaveCommittedDraftRequest
from app.presentation.schemas.work_item_schemas import (
    ForceReadyRequest,
    PagedWorkItemResponse,
    ReassignOwnerRequest,
    TransitionRequest,
    WorkItemCreateRequest,
    WorkItemResponse,
    WorkItemUpdateRequest,
)

router = APIRouter(tags=["work-items"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _response(item: object, workspace_id: UUID) -> dict[str, Any]:
    """Serialize a WorkItem domain object to the JSON response dict."""
    from app.domain.models.work_item import WorkItem as _WorkItem

    assert isinstance(item, _WorkItem)
    return WorkItemResponse.from_domain(item, workspace_id).model_dump(mode="json")


# ---------------------------------------------------------------------------
# POST /work-items
# ---------------------------------------------------------------------------


@router.post("/work-items", status_code=status.HTTP_201_CREATED)
async def create_work_item(
    body: WorkItemCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None  # guaranteed by get_scoped_session
    cmd = CreateWorkItemCommand(
        title=body.title,
        type=body.type,
        workspace_id=current_user.workspace_id,
        # EP-10: project FK not enforced yet; default to workspace_id so single-
        # project workspaces don't need to pre-create a project. Matches the
        # workspace-scoped list endpoint which ignores project_id entirely.
        project_id=body.project_id or current_user.workspace_id,
        creator_id=current_user.id,
        owner_id=body.owner_id,
        description=body.description,
        original_input=body.original_input,
        priority=body.priority,
        due_date=body.due_date,
        tags=tuple(body.tags),
        template_id=body.template_id,
        parent_work_item_id=body.parent_work_item_id,
    )
    item = await service.create(cmd)
    return _ok(_response(item, current_user.workspace_id), "Work item created")


# ---------------------------------------------------------------------------
# GET /work-items/{id}
# ---------------------------------------------------------------------------


@router.get("/work-items/{item_id}")
async def get_work_item(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    item = await service.get(item_id, current_user.workspace_id)
    return _ok(_response(item, current_user.workspace_id))


# ---------------------------------------------------------------------------
# PATCH /work-items/{id}
# ---------------------------------------------------------------------------


@router.patch("/work-items/{item_id}")
async def update_work_item(
    item_id: UUID,
    body: WorkItemUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    cmd = UpdateWorkItemCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        due_date=body.due_date,
        tags=tuple(body.tags) if body.tags is not None else None,
        original_input=body.original_input,
    )
    item = await service.update(cmd)
    return _ok(_response(item, current_user.workspace_id))


# ---------------------------------------------------------------------------
# DELETE /work-items/{id}
# ---------------------------------------------------------------------------


@router.delete("/work-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_item(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> Response:
    assert current_user.workspace_id is not None
    cmd = DeleteWorkItemCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
    )
    await service.delete(cmd)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# POST /work-items/{id}/transitions
# ---------------------------------------------------------------------------


@router.post("/work-items/{item_id}/transitions")
async def transition_work_item(
    item_id: UUID,
    body: TransitionRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    cmd = TransitionStateCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        target_state=body.target_state,
        actor_id=current_user.id,
        reason=body.reason,
    )
    item = await service.transition(cmd)
    return _ok(_response(item, current_user.workspace_id))


# ---------------------------------------------------------------------------
# POST /work-items/{id}/force-ready
# ---------------------------------------------------------------------------


@router.post("/work-items/{item_id}/force-ready")
async def force_ready_work_item(
    item_id: UUID,
    body: ForceReadyRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    cmd = ForceReadyCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        justification=body.justification,
        confirmed=body.confirmed,
    )
    item = await service.force_ready(cmd)
    return _ok(_response(item, current_user.workspace_id))


# ---------------------------------------------------------------------------
# PATCH /work-items/{id}/owner
# ---------------------------------------------------------------------------


@router.patch("/work-items/{item_id}/owner")
async def reassign_owner(
    item_id: UUID,
    body: ReassignOwnerRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    cmd = ReassignOwnerCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        new_owner_id=body.new_owner_id,
        reason=body.reason,
    )
    item = await service.reassign(cmd)
    return _ok(_response(item, current_user.workspace_id))


# ---------------------------------------------------------------------------
# GET /work-items/{id}/transitions
# ---------------------------------------------------------------------------


@router.get("/work-items/{item_id}/transitions")
async def get_transitions(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    transitions = await service.get_transitions(item_id, current_user.workspace_id)
    return _ok(
        [
            {
                "work_item_id": str(t.work_item_id),
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "actor_id": str(t.actor_id) if t.actor_id else None,
                "triggered_at": t.triggered_at.isoformat(),
                "reason": t.reason,
                "is_override": t.is_override,
                "override_justification": t.override_justification,
            }
            for t in transitions
        ]
    )


# ---------------------------------------------------------------------------
# GET /work-items/{id}/ownership-history
# ---------------------------------------------------------------------------


@router.get("/work-items/{item_id}/ownership-history")
async def get_ownership_history(
    item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    history = await service.get_ownership_history(item_id, current_user.workspace_id)
    return _ok(
        [
            {
                "work_item_id": str(r.work_item_id),
                "previous_owner_id": str(r.previous_owner_id),
                "new_owner_id": str(r.new_owner_id),
                "changed_by": str(r.changed_by),
                "changed_at": r.changed_at.isoformat(),
                "reason": r.reason,
            }
            for r in history
        ]
    )


# ---------------------------------------------------------------------------
# GET /projects/{project_id}/work-items
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# PATCH /work-items/{id}/draft  (EP-02)
# ---------------------------------------------------------------------------


@router.patch("/work-items/{item_id}/draft")
async def save_committed_draft(
    item_id: UUID,
    body: SaveCommittedDraftRequest,
    current_user: CurrentUser = Depends(get_current_user),
    draft_service: DraftService = Depends(get_draft_service),
) -> dict[str, Any]:
    from datetime import UTC, datetime

    assert current_user.workspace_id is not None
    await draft_service.save_committed_draft(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        actor_id=current_user.id,
        draft_data=body.draft_data,
    )
    return _ok(
        {"id": str(item_id), "draft_saved_at": datetime.now(UTC).isoformat()},
        "Draft saved",
    )


@router.get("/projects/{project_id}/work-items")
async def list_work_items(
    project_id: UUID,
    state: WorkItemState | None = None,
    type: WorkItemType | None = None,
    owner_id: UUID | None = None,
    has_override: bool | None = None,
    include_deleted: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    filters = WorkItemFilters(
        state=state,
        type=type,
        owner_id=owner_id,
        has_override=has_override,
        include_deleted=include_deleted,
        page=page,
        page_size=page_size,
    )
    page_result = await service.list(current_user.workspace_id, project_id, filters)
    paged = PagedWorkItemResponse(
        items=[
            WorkItemResponse.from_domain(item, current_user.workspace_id)
            for item in page_result.items
        ],
        total=page_result.total,
        page=page,
        page_size=page_size,
    )
    return _ok(paged.model_dump(mode="json"))


@router.get("/work-items")
async def list_all_work_items(
    state: WorkItemState | None = None,
    type: WorkItemType | None = None,
    owner_id: UUID | None = None,
    parent_work_item_id: UUID | None = None,
    has_override: bool | None = None,
    include_deleted: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    """List all work items in the current workspace (all projects).

    RLS ensures only workspace-scoped items are returned.
    Pass `parent_work_item_id` to return direct children of a given parent.
    """
    assert current_user.workspace_id is not None

    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.models.orm import WorkItemORM
    from app.infrastructure.persistence.session_context import with_workspace

    factory = get_session_factory()
    async with factory() as session:
        await with_workspace(session, current_user.workspace_id)
        stmt = select(WorkItemORM).where(
            WorkItemORM.workspace_id == current_user.workspace_id
        )
        if state:
            stmt = stmt.where(WorkItemORM.state == state.value)
        if type:
            stmt = stmt.where(WorkItemORM.type == type.value)
        if owner_id:
            stmt = stmt.where(WorkItemORM.owner_id == owner_id)
        if parent_work_item_id is not None:
            stmt = stmt.where(WorkItemORM.parent_work_item_id == parent_work_item_id)
        if not include_deleted:
            stmt = stmt.where(WorkItemORM.deleted_at.is_(None))
        stmt = stmt.order_by(WorkItemORM.updated_at.desc())

        from sqlalchemy import func as sa_func

        total_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await session.execute(total_stmt)).scalar_one()

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await session.execute(stmt)).scalars().all()

        from app.infrastructure.persistence.mappers.work_item_mapper import to_domain

        items = [to_domain(row) for row in rows]

    paged = PagedWorkItemResponse(
        items=[
            WorkItemResponse.from_domain(item, current_user.workspace_id)
            for item in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
    return _ok(paged.model_dump(mode="json"))
