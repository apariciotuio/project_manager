"""EP-09 — SavedSearch repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.saved_search import SavedSearch
from app.domain.repositories.saved_search_repository import ISavedSearchRepository
from app.infrastructure.persistence.mappers.saved_search_mapper import (
    saved_search_to_domain,
    saved_search_to_orm,
)
from app.infrastructure.persistence.models.orm import SavedSearchORM


class SavedSearchRepositoryImpl(ISavedSearchRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, saved_search: SavedSearch) -> SavedSearch:
        self._session.add(saved_search_to_orm(saved_search))
        await self._session.flush()
        return saved_search

    async def get(self, saved_search_id: UUID) -> SavedSearch | None:
        row = await self._session.get(SavedSearchORM, saved_search_id)
        return saved_search_to_domain(row) if row else None

    async def list_for_user(self, user_id: UUID, workspace_id: UUID) -> list[SavedSearch]:
        # User's own + shared in workspace
        stmt = (
            select(SavedSearchORM)
            .where(
                SavedSearchORM.workspace_id == workspace_id,
                or_(
                    SavedSearchORM.user_id == user_id,
                    SavedSearchORM.is_shared.is_(True),
                ),
            )
            .order_by(SavedSearchORM.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [saved_search_to_domain(r) for r in rows]

    async def list_for_workspace(self, workspace_id: UUID) -> list[SavedSearch]:
        stmt = (
            select(SavedSearchORM)
            .where(SavedSearchORM.workspace_id == workspace_id)
            .order_by(SavedSearchORM.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [saved_search_to_domain(r) for r in rows]

    async def update(self, saved_search: SavedSearch) -> SavedSearch:
        row = await self._session.get(SavedSearchORM, saved_search.id)
        if row is not None:
            row.name = saved_search.name
            row.query_params = saved_search.query_params
            row.is_shared = saved_search.is_shared
            row.updated_at = saved_search.updated_at
            await self._session.flush()
        return saved_search

    async def delete(self, saved_search_id: UUID) -> None:
        row = await self._session.get(SavedSearchORM, saved_search_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()
