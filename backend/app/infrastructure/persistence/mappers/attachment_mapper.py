"""Mappers for Attachment — EP-16."""

from __future__ import annotations

from app.domain.models.attachment import Attachment
from app.infrastructure.persistence.models.orm import AttachmentORM


def attachment_to_domain(row: AttachmentORM) -> Attachment:
    return Attachment(
        id=row.id,
        workspace_id=row.workspace_id,
        work_item_id=row.work_item_id,
        comment_id=row.comment_id,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        storage_key=row.storage_key,
        thumbnail_key=row.thumbnail_key,
        checksum_sha256=row.checksum_sha256,
        deleted_at=row.deleted_at,
        uploaded_at=row.uploaded_at,
        uploaded_by=row.uploaded_by,
    )


def attachment_to_orm(entity: Attachment) -> AttachmentORM:
    row = AttachmentORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.work_item_id = entity.work_item_id
    row.comment_id = entity.comment_id
    row.filename = entity.filename
    row.content_type = entity.content_type
    row.size_bytes = entity.size_bytes
    row.storage_key = entity.storage_key
    row.thumbnail_key = entity.thumbnail_key
    row.checksum_sha256 = entity.checksum_sha256
    row.deleted_at = entity.deleted_at
    row.uploaded_at = entity.uploaded_at
    row.uploaded_by = entity.uploaded_by
    return row
