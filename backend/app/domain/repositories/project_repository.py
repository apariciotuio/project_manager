"""EP-10 — IProjectRepository, IRoutingRuleRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.project import Project, RoutingRule


class IProjectRepository(ABC):
    @abstractmethod
    async def create(self, project: Project) -> Project: ...

    @abstractmethod
    async def get(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Project]: ...

    @abstractmethod
    async def save(self, project: Project) -> Project: ...


class IRoutingRuleRepository(ABC):
    @abstractmethod
    async def create(self, rule: RoutingRule) -> RoutingRule: ...

    @abstractmethod
    async def get(self, rule_id: UUID) -> RoutingRule | None: ...

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[RoutingRule]: ...

    @abstractmethod
    async def match(
        self,
        workspace_id: UUID,
        work_item_type: str,
        project_id: UUID | None,
    ) -> RoutingRule | None: ...

    @abstractmethod
    async def delete(self, rule_id: UUID) -> None: ...
