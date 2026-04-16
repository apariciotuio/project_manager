"""EP-16 — Attachment repository implementation."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.attachment import Attachment
from app.infrastructure.persistence.mappers.attachment_mapper import (
    attachment_to_domain,
    attachment_to_orm,
)
from app.infrastructure.persistence.models.orm import AttachmentORM


class AttachmentRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, attachment: Attachment) -> Attachment:
        self._session.add(attachment_to_orm(attachment))
        await self._session.flush()
        return attachment

    async def get(self, attachment_id: UUID) -> Attachment | None:
        row = await self._session.get(AttachmentORM, attachment_id)
        return attachment_to_domain(row) if row else None

    async def list_for_work_item(self, work_item_id: UUID) -> list[Attachment]:
        stmt = (
            select(AttachmentORM)
            .where(
                AttachmentORM.work_item_id == work_item_id,
                AttachmentORM.deleted_at.is_(None),
            )
            .order_by(AttachmentORM.uploaded_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [attachment_to_domain(r) for r in rows]

    async def list_for_comment(self, comment_id: UUID) -> list[Attachment]:
        stmt = (
            select(AttachmentORM)
            .where(
                AttachmentORM.comment_id == comment_id,
                AttachmentORM.deleted_at.is_(None),
            )
            .order_by(AttachmentORM.uploaded_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [attachment_to_domain(r) for r in rows]

    async def save(self, attachment: Attachment) -> Attachment:
        existing = await self._session.get(AttachmentORM, attachment.id)
        if existing is None:
            self._session.add(attachment_to_orm(attachment))
        else:
            existing.deleted_at = attachment.deleted_at
            existing.thumbnail_key = attachment.thumbnail_key
            existing.checksum_sha256 = attachment.checksum_sha256
        await self._session.flush()
        return attachment
