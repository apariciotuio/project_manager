"""EP-04 — SectionVersion (append-only)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.models.section_type import GenerationSource, SectionType


@dataclass(frozen=True)
class SectionVersion:
    id: UUID
    section_id: UUID
    work_item_id: UUID
    section_type: SectionType
    content: str
    version: int
    generation_source: GenerationSource
    revert_from_version: int | None
    created_at: datetime
    created_by: UUID
