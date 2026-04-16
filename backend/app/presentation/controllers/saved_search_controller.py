"""EP-09 — SavedSearch controller.

Routes:
  POST   /api/v1/saved-searches
  GET    /api/v1/saved-searches
  DELETE /api/v1/saved-searches/{saved_search_id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.domain.models.saved_search import SavedSearch
from app.presentation.dependencies import get_current_user, get_saved_search_repo
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["saved-searches"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _saved_search_payload(s: Any) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "user_id": str(s.user_id),
        "workspace_id": str(s.workspace_id),
        "name": s.name,
        "query_params": s.query_params,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


class CreateSavedSearchRequest(BaseModel):
    name: str
    query_params: dict[str, Any] | None = None


@router.post("/saved-searches", status_code=http_status.HTTP_201_CREATED)
async def create_saved_search(
    body: CreateSavedSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    repo=Depends(get_saved_search_repo),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        saved_search = SavedSearch.create(
            user_id=current_user.id,
            workspace_id=current_user.workspace_id,
            name=body.name,
            query_params=body.query_params,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    result = await repo.create(saved_search)
    return _ok(_saved_search_payload(result), "saved search created")


@router.get("/saved-searches")
async def list_saved_searches(
    current_user: CurrentUser = Depends(get_current_user),
    repo=Depends(get_saved_search_repo),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    results = await repo.list_for_user(current_user.id, current_user.workspace_id)
    return _ok([_saved_search_payload(s) for s in results])


@router.delete(
    "/saved-searches/{saved_search_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def delete_saved_search(
    saved_search_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    repo=Depends(get_saved_search_repo),
) -> None:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    existing = await repo.get(saved_search_id)
    if existing is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "saved search not found",
                    "details": {},
                }
            },
        )
    # enforce ownership
    if existing.user_id != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "FORBIDDEN",
                    "message": "not your saved search",
                    "details": {},
                }
            },
        )
    await repo.delete(saved_search_id)
