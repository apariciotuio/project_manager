"""EP-04 — ISectionRepository."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.section import Section


class ISectionRepository(ABC):
    @abstractmethod
    async def get(self, section_id: UUID) -> Section | None: ...

    @abstractmethod
    async def get_by_work_item(self, work_item_id: UUID) -> list[Section]: ...

    @abstractmethod
    async def save(self, section: Section) -> Section: ...

    @abstractmethod
    async def bulk_insert(self, sections: list[Section]) -> list[Section]: ...
