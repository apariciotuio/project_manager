"""EP-04 Phase 5 — SectionService.

Thin orchestration over Section + SectionVersion repos. Wraps the Section
mutation + append-only SectionVersion write inside a single DB transaction.
Cache is invalidated after DB commit so stale completeness scores are evicted.

EP-07 phase 3.6: VersioningService injected optionally. When present,
update_section calls create_version after a successful content change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.models.section import RequiredSectionEmptyError, Section
from app.domain.models.section_catalog import catalog_for
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.work_item_version import VersionActorType, VersionTrigger
from app.domain.ports.cache import ICache
from app.domain.repositories.section_repository import ISectionRepository
from app.domain.repositories.section_version_repository import (
    ISectionVersionRepository,
)
from app.domain.repositories.work_item_repository import IWorkItemRepository

if TYPE_CHECKING:
    from app.application.services.versioning_service import VersioningService

_COMPLETENESS_CACHE_PREFIX = "completeness:"


class SectionNotFoundError(LookupError):
    pass


class SectionForbiddenError(PermissionError):
    pass


class SectionService:
    def __init__(
        self,
        *,
        section_repo: ISectionRepository,
        section_version_repo: ISectionVersionRepository,
        work_item_repo: IWorkItemRepository,
        cache: ICache | None = None,
        versioning_service: VersioningService | None = None,
    ) -> None:
        self._sections = section_repo
        self._versions = section_version_repo
        self._work_items = work_item_repo
        self._cache = cache
        self._versioning = versioning_service

    async def _invalidate(self, work_item_id: UUID) -> None:
        if self._cache is not None:
            await self._cache.delete(f"{_COMPLETENESS_CACHE_PREFIX}{work_item_id}")

    async def list_for_work_item(self, work_item_id: UUID, workspace_id: UUID) -> list[Section]:
        work_item = await self._work_items.get(work_item_id, workspace_id)
        if work_item is None:
            raise SectionNotFoundError(f"work item {work_item_id} not found")
        return await self._sections.get_by_work_item(work_item_id)

    async def bootstrap_from_catalog(
        self,
        *,
        work_item_id: UUID,
        work_item_type,  # noqa: ANN001  — WorkItemType; type-checker sees StrEnum
        actor_id: UUID,
    ) -> list[Section]:
        """Insert default Section rows per the catalog.

        No-op if sections already exist.
        """
        existing = await self._sections.get_by_work_item(work_item_id)
        if existing:
            return existing
        configs = catalog_for(work_item_type)
        sections = [
            Section.create(
                work_item_id=work_item_id,
                section_type=cfg.section_type,
                display_order=cfg.display_order,
                is_required=cfg.required,
                created_by=actor_id,
            )
            for cfg in configs
        ]
        return await self._sections.bulk_insert(sections)

    async def update_section(
        self,
        *,
        section_id: UUID,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        new_content: str,
    ) -> Section:
        work_item = await self._work_items.get(work_item_id, workspace_id)
        if work_item is None:
            raise SectionNotFoundError(f"work item {work_item_id} not found")
        if work_item.owner_id != actor_id:
            raise SectionForbiddenError("only the work item owner can edit sections")
        section = await self._sections.get(section_id)
        if section is None or section.work_item_id != work_item_id:
            raise SectionNotFoundError(f"section {section_id} not found")
        previous_content = section.content
        section.update_content(new_content, actor_id, source=GenerationSource.MANUAL)
        await self._sections.save(section)
        await self._versions.append(section, actor_id)
        await self._invalidate(work_item_id)
        if self._versioning is not None and new_content != previous_content:
            await self._versioning.create_version(
                work_item_id=work_item_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                trigger=VersionTrigger.CONTENT_EDIT,
                actor_type=VersionActorType.HUMAN,
                commit_message=f"Updated {section.section_type.value}",
            )
        return section


__all__ = [
    "RequiredSectionEmptyError",
    "SectionForbiddenError",
    "SectionNotFoundError",
    "SectionService",
    "SectionType",
]
