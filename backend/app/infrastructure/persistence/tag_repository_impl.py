"""EP-15 — Tag and WorkItemTag repository implementations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.tag import Tag, WorkItemTag
from app.infrastructure.persistence.mappers.tag_mapper import (
    tag_to_domain,
    tag_to_orm,
    work_item_tag_to_domain,
    work_item_tag_to_orm,
)
from app.infrastructure.persistence.models.orm import TagORM, WorkItemTagORM


class TagRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, tag: Tag) -> Tag:
        self._session.add(tag_to_orm(tag))
        await self._session.flush()
        return tag

    async def get(self, tag_id: UUID) -> Tag | None:
        row = await self._session.get(TagORM, tag_id)
        return tag_to_domain(row) if row else None

    async def save(self, tag: Tag) -> Tag:
        existing = await self._session.get(TagORM, tag.id)
        if existing is None:
            self._session.add(tag_to_orm(tag))
        else:
            existing.name = tag.name
            existing.color = tag.color
            existing.archived_at = tag.archived_at
        await self._session.flush()
        return tag

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Tag]:
        stmt = (
            select(TagORM)
            .where(
                TagORM.workspace_id == workspace_id,
                TagORM.archived_at.is_(None),
            )
            .order_by(TagORM.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [tag_to_domain(r) for r in rows]

    async def list_all_for_workspace(self, workspace_id: UUID) -> list[Tag]:
        stmt = select(TagORM).where(TagORM.workspace_id == workspace_id).order_by(TagORM.name)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [tag_to_domain(r) for r in rows]

    async def search_by_prefix(self, workspace_id: UUID, prefix: str) -> list[Tag]:
        stmt = (
            select(TagORM)
            .where(
                TagORM.workspace_id == workspace_id,
                TagORM.archived_at.is_(None),
                TagORM.name.ilike(f"{prefix}%"),
            )
            .order_by(TagORM.name)
            .limit(20)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [tag_to_domain(r) for r in rows]


class WorkItemTagRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_tag(self, work_item_tag: WorkItemTag) -> WorkItemTag:
        self._session.add(work_item_tag_to_orm(work_item_tag))
        await self._session.flush()
        return work_item_tag

    async def remove_tag(self, work_item_id: UUID, tag_id: UUID) -> None:
        await self._session.execute(
            delete(WorkItemTagORM).where(
                WorkItemTagORM.work_item_id == work_item_id,
                WorkItemTagORM.tag_id == tag_id,
            )
        )
        await self._session.flush()

    async def list_for_work_item(self, work_item_id: UUID) -> list[WorkItemTag]:
        stmt = (
            select(WorkItemTagORM)
            .where(WorkItemTagORM.work_item_id == work_item_id)
            .order_by(WorkItemTagORM.created_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [work_item_tag_to_domain(r) for r in rows]
