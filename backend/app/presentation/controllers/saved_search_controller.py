"""EP-09 — SavedSearch controller.

Routes:
  POST   /api/v1/saved-searches
  GET    /api/v1/saved-searches
  GET    /api/v1/saved-searches/{id}/run
  PATCH  /api/v1/saved-searches/{id}
  DELETE /api/v1/saved-searches/{id}
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.saved_search_service import (
    SavedSearchForbidden,
    SavedSearchNotFound,
    SavedSearchService,
)
from app.domain.models.saved_search import SavedSearch
from app.presentation.dependencies import get_current_user, get_saved_search_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["saved-searches"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _payload(s: SavedSearch) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "user_id": str(s.user_id),
        "workspace_id": str(s.workspace_id),
        "name": s.name,
        "query_params": s.query_params,
        "is_shared": s.is_shared,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def _no_workspace() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
    )


class CreateSavedSearchRequest(BaseModel):
    name: str
    query_params: dict[str, Any] | None = None
    is_shared: bool = False


class UpdateSavedSearchRequest(BaseModel):
    name: str | None = None
    query_params: dict[str, Any] | None = None
    is_shared: bool | None = None


@router.post("/saved-searches", status_code=http_status.HTTP_201_CREATED)
async def create_saved_search(
    body: CreateSavedSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    try:
        result = await service.create(
            user_id=current_user.id,
            workspace_id=current_user.workspace_id,
            name=body.name,
            query_params=body.query_params,
            is_shared=body.is_shared,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_payload(result), "saved search created")


@router.get("/saved-searches")
async def list_saved_searches(
    current_user: CurrentUser = Depends(get_current_user),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    results = await service.list(
        user_id=current_user.id,
        workspace_id=current_user.workspace_id,
    )
    return _ok([_payload(s) for s in results])


@router.get("/saved-searches/{saved_search_id}/run")
async def run_saved_search(
    saved_search_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> dict[str, Any]:
    """Execute the stored query_params against work_items and return paginated results."""
    if current_user.workspace_id is None:
        raise _no_workspace()

    entity = await service.get(saved_search_id)
    if entity is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": "saved search not found", "details": {}}
            },
        )
    # Only owner or workspace member if shared
    if entity.user_id != current_user.id and not entity.is_shared:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {"code": "FORBIDDEN", "message": "not your saved search", "details": {}}
            },
        )

    # Execute the stored query by reusing the work-item list machinery
    from app.application.services.work_item_list_service import WorkItemListQueryBuilder
    from app.domain.queries.work_item_list_filters import WorkItemListFilters
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.mappers.work_item_mapper import to_domain
    from app.infrastructure.persistence.session_context import with_workspace
    from app.presentation.schemas.work_item_schemas import WorkItemResponse

    try:
        filters = WorkItemListFilters(**entity.query_params)
    except Exception:
        filters = WorkItemListFilters()

    builder = WorkItemListQueryBuilder(
        workspace_id=current_user.workspace_id,
        filters=filters,
    )

    factory = get_session_factory()
    async with factory() as session:
        await with_workspace(session, current_user.workspace_id)
        total = (await session.execute(builder.build_count_stmt())).scalar_one()
        rows = (await session.execute(builder.build_stmt())).scalars().all()
        items = [to_domain(row) for row in rows]

    has_next = len(items) > filters.limit
    if has_next:
        items = items[: filters.limit]

    return {
        "data": {
            "items": [
                WorkItemResponse.from_domain(i, current_user.workspace_id).model_dump(mode="json")
                for i in items
            ],
            "total": total,
            "has_next": has_next,
        },
        "message": "ok",
    }


@router.patch("/saved-searches/{saved_search_id}")
async def update_saved_search(
    saved_search_id: UUID,
    body: UpdateSavedSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    try:
        result = await service.update(
            saved_search_id=saved_search_id,
            requesting_user_id=current_user.id,
            name=body.name,
            query_params=body.query_params,
            is_shared=body.is_shared,
        )
    except SavedSearchNotFound as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": "saved search not found", "details": {}}
            },
        ) from exc
    except SavedSearchForbidden as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {"code": "FORBIDDEN", "message": "not your saved search", "details": {}}
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_payload(result))


@router.delete(
    "/saved-searches/{saved_search_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def delete_saved_search(
    saved_search_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: SavedSearchService = Depends(get_saved_search_service),
) -> None:
    if current_user.workspace_id is None:
        raise _no_workspace()
    try:
        await service.delete(
            saved_search_id=saved_search_id,
            requesting_user_id=current_user.id,
        )
    except SavedSearchNotFound as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": "saved search not found", "details": {}}
            },
        ) from exc
    except SavedSearchForbidden as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {"code": "FORBIDDEN", "message": "not your saved search", "details": {}}
            },
        ) from exc
