"""EP-04 — ISectionVersionRepository (append-only)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.section import Section
from app.domain.models.section_version import SectionVersion


class ISectionVersionRepository(ABC):
    @abstractmethod
    async def append(self, section: Section, actor_id: UUID) -> SectionVersion: ...

    @abstractmethod
    async def get_history(self, section_id: UUID) -> list[SectionVersion]: ...
