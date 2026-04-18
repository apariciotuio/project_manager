"""EP-09 — SavedSearchService.

Thin orchestration layer for saved search CRUD + run.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.models.saved_search import SavedSearch
from app.domain.repositories.saved_search_repository import ISavedSearchRepository


class SavedSearchService:
    def __init__(self, repo: ISavedSearchRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        name: str,
        query_params: dict[str, Any] | None = None,
        is_shared: bool = False,
    ) -> SavedSearch:
        entity = SavedSearch.create(
            user_id=user_id,
            workspace_id=workspace_id,
            name=name,
            query_params=query_params,
            is_shared=is_shared,
        )
        return await self._repo.create(entity)

    async def list(self, *, user_id: UUID, workspace_id: UUID) -> list[SavedSearch]:
        return await self._repo.list_for_user(user_id, workspace_id)

    async def get(self, saved_search_id: UUID) -> SavedSearch | None:
        return await self._repo.get(saved_search_id)

    async def update(
        self,
        *,
        saved_search_id: UUID,
        requesting_user_id: UUID,
        name: str | None = None,
        query_params: dict[str, Any] | None = None,
        is_shared: bool | None = None,
    ) -> SavedSearch:
        entity = await self._repo.get(saved_search_id)
        if entity is None:
            raise SavedSearchNotFound(saved_search_id)
        if entity.user_id != requesting_user_id:
            raise SavedSearchForbidden(saved_search_id)
        entity.update(name=name, query_params=query_params, is_shared=is_shared)
        return await self._repo.update(entity)

    async def delete(
        self,
        *,
        saved_search_id: UUID,
        requesting_user_id: UUID,
    ) -> None:
        entity = await self._repo.get(saved_search_id)
        if entity is None:
            raise SavedSearchNotFound(saved_search_id)
        if entity.user_id != requesting_user_id:
            raise SavedSearchForbidden(saved_search_id)
        await self._repo.delete(saved_search_id)


class SavedSearchNotFound(Exception):
    def __init__(self, saved_search_id: UUID) -> None:
        super().__init__(f"saved search {saved_search_id} not found")
        self.saved_search_id = saved_search_id


class SavedSearchForbidden(Exception):
    def __init__(self, saved_search_id: UUID) -> None:
        super().__init__(f"not authorized to modify saved search {saved_search_id}")
        self.saved_search_id = saved_search_id
