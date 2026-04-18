"""EP-04 — Section entity.

One row per (work_item_id, section_type). Mutable content; version increments
on every save. An append-only SectionVersion row is written before overwriting
content (see SectionRepository.save).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.models.section_type import GenerationSource, SectionType


class RequiredSectionEmptyError(Exception):
    """Raised when attempting to save an empty string into a required section."""


@dataclass
class Section:
    id: UUID
    work_item_id: UUID
    section_type: SectionType
    content: str
    display_order: int
    is_required: bool
    generation_source: GenerationSource
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID
    updated_by: UUID
    workspace_id: UUID | None = None

    def update_content(
        self,
        new_content: str,
        actor_id: UUID,
        source: GenerationSource = GenerationSource.MANUAL,
    ) -> None:
        """Mutate in place; caller is responsible for persistence.

        Empty content on a required section raises RequiredSectionEmptyError.
        """
        if self.is_required and not new_content.strip():
            raise RequiredSectionEmptyError(
                f"Section {self.section_type.value} is required and cannot be empty"
            )
        self.content = new_content
        self.generation_source = source
        self.updated_by = actor_id
        self.updated_at = datetime.now(UTC)
        self.version += 1

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        section_type: SectionType,
        display_order: int,
        is_required: bool,
        created_by: UUID,
        content: str = "",
        generation_source: GenerationSource = GenerationSource.LLM,
    ) -> Section:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            section_type=section_type,
            content=content,
            display_order=display_order,
            is_required=is_required,
            generation_source=generation_source,
            version=1,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            updated_by=created_by,
        )
