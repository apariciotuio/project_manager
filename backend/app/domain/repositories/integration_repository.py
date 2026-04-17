"""EP-11 — IIntegrationConfigRepository, IIntegrationExportRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.integration import IntegrationConfig, IntegrationExport


class IIntegrationConfigRepository(ABC):
    @abstractmethod
    async def create(self, config: IntegrationConfig) -> IntegrationConfig: ...

    @abstractmethod
    async def get(self, config_id: UUID) -> IntegrationConfig | None: ...

    @abstractmethod
    async def list_active_for_workspace(
        self, workspace_id: UUID
    ) -> list[IntegrationConfig]: ...

    @abstractmethod
    async def save(self, config: IntegrationConfig) -> IntegrationConfig: ...

    @abstractmethod
    async def delete(self, config_id: UUID) -> None: ...


class IIntegrationExportRepository(ABC):
    @abstractmethod
    async def create(self, export: IntegrationExport) -> IntegrationExport: ...

    @abstractmethod
    async def get(self, export_id: UUID) -> IntegrationExport | None: ...

    @abstractmethod
    async def get_by_work_item(self, work_item_id: UUID) -> list[IntegrationExport]: ...

    @abstractmethod
    async def get_by_external_key(
        self, external_key: str, integration_config_id: UUID
    ) -> IntegrationExport | None: ...
