"""Repository interface for ContextPreset."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.context_preset import ContextPreset


class IContextPresetRepository(ABC):
    @abstractmethod
    async def create(self, preset: ContextPreset) -> ContextPreset: ...

    @abstractmethod
    async def get_by_id(self, preset_id: UUID, workspace_id: UUID) -> ContextPreset | None: ...

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[ContextPreset]: ...

    @abstractmethod
    async def save(self, preset: ContextPreset) -> ContextPreset: ...

    @abstractmethod
    async def get_by_name(
        self, workspace_id: UUID, name: str
    ) -> ContextPreset | None: ...
