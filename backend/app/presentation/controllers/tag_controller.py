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

from app.domain.errors.codes import (
    InvalidInputError,
    NotFoundError,
    TagArchivedDomainError,
    TagNameTakenError,
)
from app.domain.models.tag import Tag, TagArchivedError, WorkItemTag
from app.infrastructure.persistence.models.orm import WorkItemORM
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


def _no_workspace() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
    )


class CreateTagRequest(BaseModel):
    name: str
    color: str | None = None


class UpdateTagRequest(BaseModel):
    name: str | None = None
    color: str | None = None
    archived: bool | None = None


class AddTagToWorkItemRequest(BaseModel):
    tag_id: UUID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_tag_scoped(
    tag_id: UUID,
    workspace_id: UUID,
    repo: TagRepositoryImpl,
) -> Tag:
    """Fetch tag and verify workspace ownership. Raises NotFoundError on miss or scope violation."""
    tag = await repo.get(tag_id)
    if tag is None or tag.workspace_id != workspace_id:
        raise NotFoundError("tag not found")
    return tag


async def _assert_work_item_scoped(
    work_item_id: UUID,
    workspace_id: UUID,
    session: AsyncSession,
) -> None:
    """Assert work item exists and belongs to this workspace. Raises NotFoundError otherwise."""
    row = await session.get(WorkItemORM, work_item_id)
    if row is None or row.workspace_id != workspace_id:
        raise NotFoundError("work item not found")


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
        raise _no_workspace()
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
        raise _no_workspace()
    repo = TagRepositoryImpl(session)
    if prefix:
        tags = await repo.search_by_prefix(current_user.workspace_id, prefix)
    else:
        tags = await repo.list_active_for_workspace(current_user.workspace_id)
    return _ok([_tag_payload(t) for t in tags])


@router.patch("/tags/{tag_id}")
async def update_tag(
    tag_id: UUID,
    body: UpdateTagRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    if body.name is None and body.color is None and body.archived is None:
        raise InvalidInputError("at least one of name, color, or archived must be provided")
    repo = TagRepositoryImpl(session)
    tag = await _get_tag_scoped(tag_id, current_user.workspace_id, repo)

    # Apply only fields that were provided
    if body.name is not None:
        try:
            tag.rename(body.name)
        except TagArchivedError as exc:
            raise TagArchivedDomainError(str(exc)) from exc
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
    if body.color is not None:
        if tag.is_archived:
            raise TagArchivedDomainError("Cannot update color of an archived tag")
        tag.color = body.color
    if body.archived is True:
        tag.archive()

    try:
        saved = await repo.save(tag)
    except IntegrityError as exc:
        raise TagNameTakenError(body.name or "") from exc
    return _ok(_tag_payload(saved))


@router.delete("/tags/{tag_id}", status_code=http_status.HTTP_200_OK)
async def archive_tag(
    tag_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    repo = TagRepositoryImpl(session)
    tag = await _get_tag_scoped(tag_id, current_user.workspace_id, repo)
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
    if current_user.workspace_id is None:
        raise _no_workspace()
    await _assert_work_item_scoped(work_item_id, current_user.workspace_id, session)

    # Verify tag exists, is not archived, and belongs to same workspace
    tag_repo = TagRepositoryImpl(session)
    tag = await _get_tag_scoped(body.tag_id, current_user.workspace_id, tag_repo)
    if tag.is_archived:
        raise TagArchivedDomainError("cannot attach archived tag")

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
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    await _assert_work_item_scoped(work_item_id, current_user.workspace_id, session)
    repo = WorkItemTagRepositoryImpl(session)
    await repo.remove_tag(work_item_id, tag_id)
    return _ok({"work_item_id": str(work_item_id), "tag_id": str(tag_id)}, "tag removed")


@router.get("/work-items/{work_item_id}/tags")
async def list_work_item_tags(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise _no_workspace()
    await _assert_work_item_scoped(work_item_id, current_user.workspace_id, session)
    repo = WorkItemTagRepositoryImpl(session)
    wits = await repo.list_for_work_item(work_item_id)
    return _ok([_work_item_tag_payload(w) for w in wits])
