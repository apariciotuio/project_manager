"""EP-07 — SQLAlchemy implementation for Comment repo."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.comment import Comment
from app.domain.repositories.comment_repository import ICommentRepository
from app.infrastructure.persistence.mappers.comment_mapper import (
    comment_to_domain,
    comment_to_orm,
)
from app.infrastructure.persistence.models.orm import CommentORM


class CommentRepositoryImpl(ICommentRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, comment: Comment) -> Comment:
        self._session.add(comment_to_orm(comment))
        await self._session.flush()
        return comment

    async def get(self, comment_id: UUID) -> Comment | None:
        row = await self._session.get(CommentORM, comment_id)
        return comment_to_domain(row) if row else None

    async def list_for_work_item(self, work_item_id: UUID) -> list[Comment]:
        stmt = (
            select(CommentORM)
            .where(
                CommentORM.work_item_id == work_item_id,
                CommentORM.deleted_at.is_(None),
            )
            .order_by(CommentORM.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [comment_to_domain(r) for r in rows]

    async def save(self, comment: Comment) -> Comment:
        existing = await self._session.get(CommentORM, comment.id)
        if existing is None:
            self._session.add(comment_to_orm(comment))
        else:
            existing.body = comment.body
            existing.is_edited = comment.is_edited
            existing.edited_at = comment.edited_at
            existing.deleted_at = comment.deleted_at
            existing.anchor_status = comment.anchor_status.value
        await self._session.flush()
        return comment
