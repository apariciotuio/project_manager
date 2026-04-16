"""EP-16 — Attachment domain model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


class AttachmentNotFoundError(Exception):
    pass


@dataclass
class Attachment:
    id: UUID
    workspace_id: UUID
    work_item_id: UUID | None
    comment_id: UUID | None
    filename: str
    content_type: str
    size_bytes: int
    storage_key: str
    thumbnail_key: str | None
    checksum_sha256: str | None
    deleted_at: datetime | None
    uploaded_at: datetime
    uploaded_by: UUID

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        if self.deleted_at is not None:
            return
        self.deleted_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        uploaded_by: UUID,
        filename: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        work_item_id: UUID | None = None,
        comment_id: UUID | None = None,
        thumbnail_key: str | None = None,
        checksum_sha256: str | None = None,
    ) -> Attachment:
        if not filename.strip():
            raise ValueError("Filename cannot be empty")
        if size_bytes < 0:
            raise ValueError("size_bytes must be >= 0")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            comment_id=comment_id,
            filename=filename.strip(),
            content_type=content_type,
            size_bytes=size_bytes,
            storage_key=storage_key,
            thumbnail_key=thumbnail_key,
            checksum_sha256=checksum_sha256,
            deleted_at=None,
            uploaded_at=datetime.now(UTC),
            uploaded_by=uploaded_by,
        )
