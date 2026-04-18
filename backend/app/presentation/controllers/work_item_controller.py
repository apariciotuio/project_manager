"""EP-01 Phase 4 — Work Item controller.

Thin HTTP handlers: validate → build command → call service → envelope response.
Zero business logic here.

workspace_id is guaranteed non-None by get_scoped_session — it raises 401 before
reaching any handler if the JWT has no workspace_id claim.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

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
    get_scoped_session,
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
    cmd = TransitionStateCommand(
        item_id=item_id,
        workspace_id=current_user.workspace_id,
        target_state=body.target_state,
        actor_id=current_user.id,
        reason=body.reason,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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

    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )
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

    # Fetch lock info for all items in a single query (no N+1)
    from app.infrastructure.persistence.lock_repository_impl import SectionLockRepositoryImpl
    from app.presentation.schemas.work_item_schemas import LockSummary

    lock_repo = SectionLockRepositoryImpl(session)
    work_item_ids = [item.id for item in page_result.items]
    lock_info = await lock_repo.get_lock_info_by_work_item_ids(work_item_ids)

    # Hydrate responses with lock_summary
    items = []
    for item in page_result.items:
        lock_summary = None
        if item.id in lock_info:
            info = lock_info[item.id]
            lock_summary = LockSummary(
                has_locks=True,
                count=info["count"],
                held_by_me=(info["held_by"] == current_user.id),
            )
        else:
            lock_summary = LockSummary(has_locks=False, count=0, held_by_me=False)
        items.append(
            WorkItemResponse.from_domain(item, current_user.workspace_id, lock_summary=lock_summary)
        )

    paged = PagedWorkItemResponse(
        items=items,
        total=page_result.total,
        page=page,
        page_size=page_size,
    )
    return _ok(paged.model_dump(mode="json"))


@router.get("/work-items")
async def list_all_work_items(  # noqa: PLR0913
    # --- existing filters (preserved for backward compat) ---
    state: list[WorkItemState] | None = Query(default=None),
    type: list[WorkItemType] | None = Query(default=None),
    owner_id: UUID | None = None,
    parent_work_item_id: UUID | None = None,
    has_override: bool | None = None,
    include_deleted: bool = False,
    # --- new EP-09 filters ---
    project_id: UUID | None = None,
    creator_id: UUID | None = None,
    tag_id: list[str] | None = Query(default=None),
    priority: list[str] | None = Query(default=None),
    completeness_min: int | None = Query(default=None, ge=0, le=100),
    completeness_max: int | None = Query(default=None, ge=0, le=100),
    updated_after: str | None = None,
    updated_before: str | None = None,
    sort: str = "updated_desc",
    # --- keyset cursor pagination (preferred) ---
    cursor: str | None = None,
    page_size: int = Query(default=20, ge=1, le=100),
    # --- legacy cursor param alias (backward compat) ---
    limit: int = Query(default=20, ge=1, le=100),
    # --- legacy offset pagination ---
    page: int = Query(default=1, ge=1),
    # --- free text + puppet ---
    q: str | None = None,
    use_puppet: bool = False,
    # --- mine filter (EP-09) ---
    mine: bool = False,
    mine_type: str = "any",
    current_user: CurrentUser = Depends(get_current_user),
    service: WorkItemService = Depends(get_work_item_service),
) -> dict[str, Any]:
    """List all work items in the current workspace (all projects).

    Supports cursor-based pagination (preferred) via `cursor` + `page_size` (default 20, max 100).
    Legacy `page` / `limit` params are kept for backward compat.

    New EP-09 filters: project_id, creator_id, tag_id (AND), priority,
    completeness_min/max, updated_after/before, sort (enum), q (free-text).
    Set use_puppet=true with q to delegate to Puppet semantic search.
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}
            },
        )

    from app.domain.queries.work_item_list_filters import SortOption, WorkItemListFilters

    # Validate cursor format eagerly so we return 422 before hitting the DB.
    if cursor is not None:
        try:
            from app.domain.pagination import PaginationCursor as DomainCursor

            DomainCursor.decode(cursor)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CURSOR", "message": str(exc), "details": {}}},
            ) from exc

    # Parse sort param — default to updated_desc if unrecognised.
    try:
        sort_opt = SortOption(sort)
    except ValueError:
        sort_opt = SortOption.updated_desc

    # Build filter struct from query params.
    # updated_after / updated_before accepted as ISO strings by WorkItemListFilters.
    from app.domain.queries.work_item_list_filters import MineType

    # Validate mine_type — 422 if unrecognised
    try:
        mine_type_enum = MineType(mine_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "INVALID_MINE_TYPE",
                    "message": f"mine_type must be one of: {[e.value for e in MineType]}",
                    "details": {},
                }
            },
        ) from exc

    list_filters = WorkItemListFilters(
        state=[s.value for s in state] if state else None,
        type=[t.value for t in type] if type else None,
        owner_id=owner_id,
        parent_work_item_id=parent_work_item_id,
        has_override=has_override,
        include_deleted=include_deleted,
        project_id=project_id,
        creator_id=creator_id,
        tag_id=tag_id,
        priority=priority,
        completeness_min=completeness_min,
        completeness_max=completeness_max,
        updated_after=updated_after,  # type: ignore[arg-type]
        updated_before=updated_before,  # type: ignore[arg-type]
        sort=sort_opt,
        cursor=cursor,
        limit=page_size,
        q=q,
        use_puppet=use_puppet,
        mine=mine,
        mine_type=mine_type_enum,
    )

    result = await service.list_cursor(
        current_user.workspace_id,
        cursor=None,  # cursor is encoded inside list_filters.cursor
        page_size=page_size,
        filters=list_filters,
        current_user_id=current_user.id,
    )

    next_cursor = result.next_cursor
    has_next = result.has_next
    items = result.rows  # already domain WorkItem objects

    # Applied filters for response transparency
    applied_filters: dict[str, Any] = {}
    if state:
        applied_filters["state"] = [s.value for s in state]
    if type:
        applied_filters["type"] = [t.value for t in type]
    if owner_id:
        applied_filters["owner_id"] = str(owner_id)
    if creator_id:
        applied_filters["creator_id"] = str(creator_id)
    if project_id:
        applied_filters["project_id"] = str(project_id)
    if priority:
        applied_filters["priority"] = priority
    if q:
        applied_filters["q"] = q
    if mine:
        applied_filters["mine"] = {"type": mine_type, "user_id": str(current_user.id)}

    return {
        "data": {
            "items": [
                WorkItemResponse.from_domain(item, current_user.workspace_id).model_dump(
                    mode="json"
                )
                for item in items
            ],
            "next_cursor": next_cursor,
        },
        "pagination": {
            "cursor": next_cursor,
            "has_next": has_next,
            "total_count": None,
        },
        "applied_filters": applied_filters,
        "message": "ok",
    }
