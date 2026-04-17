"""EP-15 — Tag and WorkItemTag controller.

Routes:
  POST   /api/v1/tags
  GET    /api/v1/tags
  PATCH  /api/v1/tags/{tag_id}
  DELETE /api/v1/tags/{tag_id}           — archive

  POST   /api/v1/work-items/{id}/tags
  DELETE /api/v1/work-items/{id}/tags/{tag_id}
  GET    /api/v1/work-items/{id}/tags
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors.codes import TagNameTakenError
from app.domain.models.tag import Tag, TagArchivedError, WorkItemTag
from app.infrastructure.persistence.tag_repository_impl import (
    TagRepositoryImpl,
    WorkItemTagRepositoryImpl,
)
from app.presentation.dependencies import get_current_user, get_scoped_session
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tags"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _tag_payload(tag: Tag) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "workspace_id": str(tag.workspace_id),
        "name": tag.name,
        "color": tag.color,
        "is_archived": tag.is_archived,
        "archived_at": tag.archived_at.isoformat() if tag.archived_at else None,
        "created_at": tag.created_at.isoformat(),
        "created_by": str(tag.created_by),
    }


def _work_item_tag_payload(wit: WorkItemTag) -> dict[str, Any]:
    return {
        "id": str(wit.id),
        "work_item_id": str(wit.work_item_id),
        "tag_id": str(wit.tag_id),
        "created_at": wit.created_at.isoformat(),
        "created_by": str(wit.created_by),
    }


class CreateTagRequest(BaseModel):
    name: str
    color: str | None = None


class RenameTagRequest(BaseModel):
    name: str


class AddTagToWorkItemRequest(BaseModel):
    tag_id: UUID


# ---------------------------------------------------------------------------
# Tag CRUD
# ---------------------------------------------------------------------------


@router.post("/tags", status_code=http_status.HTTP_201_CREATED)
async def create_tag(
    body: CreateTagRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    tag = Tag.create(
        workspace_id=current_user.workspace_id,
        name=body.name,
        created_by=current_user.id,
        color=body.color,
    )
    repo = TagRepositoryImpl(session)
    try:
        saved = await repo.create(tag)
    except IntegrityError as exc:
        raise TagNameTakenError(body.name) from exc
    return _ok(_tag_payload(saved), "tag created")


@router.get("/tags")
async def list_tags(
    prefix: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    repo = TagRepositoryImpl(session)
    if prefix:
        tags = await repo.search_by_prefix(current_user.workspace_id, prefix)
    else:
        tags = await repo.list_active_for_workspace(current_user.workspace_id)
    return _ok([_tag_payload(t) for t in tags])


@router.patch("/tags/{tag_id}")
async def rename_tag(
    tag_id: UUID,
    body: RenameTagRequest,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = TagRepositoryImpl(session)
    tag = await repo.get(tag_id)
    if tag is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "tag not found", "details": {}}},
        )
    try:
        tag.rename(body.name)
    except TagArchivedError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "TAG_ARCHIVED", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    saved = await repo.save(tag)
    return _ok(_tag_payload(saved))


@router.delete("/tags/{tag_id}", status_code=http_status.HTTP_200_OK)
async def archive_tag(
    tag_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = TagRepositoryImpl(session)
    tag = await repo.get(tag_id)
    if tag is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "tag not found", "details": {}}},
        )
    tag.archive()
    await repo.save(tag)
    return _ok({"id": str(tag_id)}, "tag archived")


# ---------------------------------------------------------------------------
# WorkItem <-> Tag
# ---------------------------------------------------------------------------


@router.post("/work-items/{work_item_id}/tags", status_code=http_status.HTTP_201_CREATED)
async def add_tag_to_work_item(
    work_item_id: UUID,
    body: AddTagToWorkItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    # Verify tag exists and is not archived
    tag_repo = TagRepositoryImpl(session)
    tag = await tag_repo.get(body.tag_id)
    if tag is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "tag not found", "details": {}}},
        )
    if tag.is_archived:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "TAG_ARCHIVED",
                    "message": "cannot attach archived tag",
                    "details": {},
                }
            },
        )
    wit = WorkItemTag.create(
        work_item_id=work_item_id,
        tag_id=body.tag_id,
        created_by=current_user.id,
    )
    repo = WorkItemTagRepositoryImpl(session)
    saved = await repo.add_tag(wit)
    return _ok(_work_item_tag_payload(saved), "tag attached")


@router.delete(
    "/work-items/{work_item_id}/tags/{tag_id}",
    status_code=http_status.HTTP_200_OK,
)
async def remove_tag_from_work_item(
    work_item_id: UUID,
    tag_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = WorkItemTagRepositoryImpl(session)
    await repo.remove_tag(work_item_id, tag_id)
    return _ok({"work_item_id": str(work_item_id), "tag_id": str(tag_id)}, "tag removed")


@router.get("/work-items/{work_item_id}/tags")
async def list_work_item_tags(
    work_item_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = WorkItemTagRepositoryImpl(session)
    wits = await repo.list_for_work_item(work_item_id)
    return _ok([_work_item_tag_payload(w) for w in wits])
