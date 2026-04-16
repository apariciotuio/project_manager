"""ITemplateRepository — domain-layer interface for template persistence."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.template import Template
from app.domain.value_objects.work_item_type import WorkItemType


class ITemplateRepository(ABC):
    @abstractmethod
    async def get_by_workspace_and_type(
        self, workspace_id: UUID, type: WorkItemType
    ) -> Template | None:
        """Return workspace-specific template for the given type, or None."""

    @abstractmethod
    async def get_system_default(self, type: WorkItemType) -> Template | None:
        """Return the system default template for the given type, or None."""

    @abstractmethod
    async def get_by_id(self, template_id: UUID) -> Template | None:
        """Return template by primary key, or None."""

    @abstractmethod
    async def create(self, template: Template) -> Template:
        """Persist a new template. Raises DuplicateTemplateError on constraint violation."""

    @abstractmethod
    async def update(
        self, template_id: UUID, *, name: str | None, content: str | None
    ) -> Template:
        """Update mutable fields. Raises TemplateNotFoundError if absent."""

    @abstractmethod
    async def delete(self, template_id: UUID) -> None:
        """Hard delete. Raises TemplateNotFoundError if absent."""

    @abstractmethod
    async def list_for_workspace(self, workspace_id: UUID) -> list[Template]:
        """Return all templates for a workspace (excluding system templates)."""
