"""EP-16 — Attachment repository interface."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.attachment import Attachment


class IAttachmentRepository(Protocol):
    async def create(self, attachment: Attachment) -> Attachment: ...

    async def get(self, attachment_id: UUID) -> Attachment | None: ...

    async def list_for_work_item(self, work_item_id: UUID) -> list[Attachment]: ...

    async def list_for_comment(self, comment_id: UUID) -> list[Attachment]: ...

    async def save(self, attachment: Attachment) -> Attachment: ...
