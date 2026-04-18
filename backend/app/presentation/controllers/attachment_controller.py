"""EP-16 — Attachment controller.

Routes:
  POST   /api/v1/work-items/{id}/attachments   — register metadata; actual upload via presigned URL
  GET    /api/v1/work-items/{id}/attachments   — list
  DELETE /api/v1/attachments/{id}              — soft-delete
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.attachment import Attachment
from app.infrastructure.persistence.attachment_repository_impl import AttachmentRepositoryImpl
from app.presentation.dependencies import get_current_user, get_scoped_session
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["attachments"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _attachment_payload(a: Attachment) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "workspace_id": str(a.workspace_id),
        "work_item_id": str(a.work_item_id) if a.work_item_id else None,
        "comment_id": str(a.comment_id) if a.comment_id else None,
        "filename": a.filename,
        "content_type": a.content_type,
        "size_bytes": a.size_bytes,
        "storage_key": a.storage_key,
        "thumbnail_key": a.thumbnail_key,
        "checksum_sha256": a.checksum_sha256,
        "uploaded_at": a.uploaded_at.isoformat(),
        "uploaded_by": str(a.uploaded_by),
    }


class RegisterAttachmentRequest(BaseModel):
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    thumbnail_key: str | None = None
    checksum_sha256: str | None = None


@router.post("/work-items/{work_item_id}/attachments", status_code=http_status.HTTP_201_CREATED)
async def register_attachment(
    work_item_id: UUID,
    body: RegisterAttachmentRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        attachment = Attachment.create(
            workspace_id=current_user.workspace_id,
            uploaded_by=current_user.id,
            filename=body.filename,
            content_type=body.content_type,
            size_bytes=body.size_bytes,
            storage_key=body.storage_key,
            work_item_id=work_item_id,
            thumbnail_key=body.thumbnail_key,
            checksum_sha256=body.checksum_sha256,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    repo = AttachmentRepositoryImpl(session)
    saved = await repo.create(attachment)
    return _ok(_attachment_payload(saved), "attachment registered")


@router.get("/work-items/{work_item_id}/attachments")
async def list_attachments(
    work_item_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = AttachmentRepositoryImpl(session)
    attachments = await repo.list_for_work_item(work_item_id)
    return _ok([_attachment_payload(a) for a in attachments])


@router.delete("/attachments/{attachment_id}", status_code=http_status.HTTP_200_OK)
async def delete_attachment(
    attachment_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    repo = AttachmentRepositoryImpl(session)
    attachment = await repo.get(attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {"code": "NOT_FOUND", "message": "attachment not found", "details": {}}
            },
        )
    attachment.soft_delete()
    await repo.save(attachment)
    return _ok({"id": str(attachment_id)}, "attachment deleted")
