"""Repository interface for JiraConfig."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.jira_config import JiraConfig, JiraProjectMapping


class IJiraConfigRepository(ABC):
    @abstractmethod
    async def create(self, config: JiraConfig) -> JiraConfig: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID, workspace_id: UUID) -> JiraConfig | None: ...

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[JiraConfig]: ...

    @abstractmethod
    async def save(self, config: JiraConfig) -> JiraConfig: ...

    @abstractmethod
    async def get_active_for_workspace(
        self, workspace_id: UUID, project_id: UUID | None = None
    ) -> JiraConfig | None:
        """Return workspace-level or project-level config (project_id=None = workspace-level)."""
        ...

    # --- mappings ---

    @abstractmethod
    async def create_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping: ...

    @abstractmethod
    async def get_mapping_by_id(
        self, mapping_id: UUID, workspace_id: UUID
    ) -> JiraProjectMapping | None: ...

    @abstractmethod
    async def list_mappings(self, config_id: UUID) -> list[JiraProjectMapping]: ...

    @abstractmethod
    async def save_mapping(self, mapping: JiraProjectMapping) -> JiraProjectMapping: ...

    @abstractmethod
    async def delete_mapping(self, mapping_id: UUID, workspace_id: UUID) -> None: ...
