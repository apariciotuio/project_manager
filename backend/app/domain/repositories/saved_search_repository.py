"""EP-09 — ISavedSearchRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.saved_search import SavedSearch


class ISavedSearchRepository(ABC):
    @abstractmethod
    async def create(self, saved_search: SavedSearch) -> SavedSearch: ...

    @abstractmethod
    async def get(self, saved_search_id: UUID) -> SavedSearch | None: ...

    @abstractmethod
    async def list_for_user(
        self, user_id: UUID, workspace_id: UUID
    ) -> list[SavedSearch]: ...

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[SavedSearch]: ...

    @abstractmethod
    async def update(self, saved_search: SavedSearch) -> SavedSearch: ...

    @abstractmethod
    async def delete(self, saved_search_id: UUID) -> None: ...
