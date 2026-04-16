"""Abstract interface for Workspace persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.workspace import Workspace


class IWorkspaceRepository(ABC):
    @abstractmethod
    async def create(self, workspace: Workspace) -> Workspace: ...

    @abstractmethod
    async def get_by_id(self, workspace_id: UUID) -> Workspace | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Workspace | None: ...

    @abstractmethod
    async def slug_exists(self, slug: str) -> bool: ...
