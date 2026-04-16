"""EP-07 — Comment controller.

Routes:
  POST   /api/v1/work-items/{id}/comments  — create
  GET    /api/v1/work-items/{id}/comments  — list (exclude deleted)
  PATCH  /api/v1/comments/{id}             — edit
  DELETE /api/v1/comments/{id}             — soft-delete
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.comment_service import (
    CommentForbiddenError,
    CommentNotFoundError,
    CommentService,
)
from app.domain.models.comment import AnchorInvalidError, Comment, NestingExceededError
from app.presentation.dependencies import get_comment_service, get_current_user
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateCommentBody(BaseModel):
    body: str
    parent_comment_id: UUID | None = None
    anchor_section_id: UUID | None = None
    anchor_start_offset: int | None = None
    anchor_end_offset: int | None = None
    anchor_snapshot_text: str | None = None


class EditCommentBody(BaseModel):
    body: str


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _comment_payload(c: Comment) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "work_item_id": str(c.work_item_id),
        "parent_comment_id": str(c.parent_comment_id) if c.parent_comment_id else None,
        "body": c.body,
        "actor_type": c.actor_type.value,
        "actor_id": str(c.actor_id) if c.actor_id else None,
        "anchor_section_id": str(c.anchor_section_id) if c.anchor_section_id else None,
        "anchor_start_offset": c.anchor_start_offset,
        "anchor_end_offset": c.anchor_end_offset,
        "anchor_snapshot_text": c.anchor_snapshot_text,
        "anchor_status": c.anchor_status.value,
        "is_edited": c.is_edited,
        "edited_at": c.edited_at.isoformat() if c.edited_at else None,
        "created_at": c.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/work-items/{work_item_id}/comments", status_code=http_status.HTTP_201_CREATED)
async def create_comment(
    work_item_id: UUID,
    body: CreateCommentBody,
    current_user: CurrentUser = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        comment = await service.create(
            work_item_id=work_item_id,
            body=body.body,
            actor_id=current_user.id,
            parent_comment_id=body.parent_comment_id,
            anchor_section_id=body.anchor_section_id,
            anchor_start_offset=body.anchor_start_offset,
            anchor_end_offset=body.anchor_end_offset,
            anchor_snapshot_text=body.anchor_snapshot_text,
        )
    except NestingExceededError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": "NESTING_EXCEEDED", "message": str(exc), "details": {}}
            },
        ) from exc
    except CommentNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except AnchorInvalidError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": "ANCHOR_INVALID", "message": str(exc), "details": {}}
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_comment_payload(comment), "comment created")


@router.get("/work-items/{work_item_id}/comments")
async def list_comments(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    comments = await service.list_for_work_item(work_item_id)
    return _ok([_comment_payload(c) for c in comments])


@router.patch("/comments/{comment_id}")
async def edit_comment(
    comment_id: UUID,
    body: EditCommentBody,
    current_user: CurrentUser = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        comment = await service.edit(
            comment_id=comment_id,
            new_body=body.body,
            actor_id=current_user.id,
        )
    except CommentNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except CommentForbiddenError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "VALIDATION_ERROR", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_comment_payload(comment), "comment updated")


@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: CommentService = Depends(get_comment_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        comment = await service.delete(
            comment_id=comment_id,
            actor_id=current_user.id,
        )
    except CommentNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except CommentForbiddenError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_comment_payload(comment), "comment deleted")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_workspace(user: CurrentUser) -> None:
    if user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
