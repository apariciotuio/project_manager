"""EP-10 — ValidationRuleTemplate domain entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

_REQUIREMENT_TYPES = frozenset(
    ["section_content", "reviewer_approval", "validator_approval", "custom"]
)


@dataclass
class ValidationRuleTemplate:
    id: UUID
    workspace_id: UUID | None  # None = global system template
    name: str
    work_item_type: str | None  # None = applies to any type
    requirement_type: str
    default_dimension: str | None
    default_description: str | None
    is_mandatory: bool
    active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: str,
        requirement_type: str,
        is_mandatory: bool,
        workspace_id: UUID | None = None,
        work_item_type: str | None = None,
        default_dimension: str | None = None,
        default_description: str | None = None,
        active: bool = True,
    ) -> ValidationRuleTemplate:
        if not name.strip():
            raise ValueError("name cannot be empty")
        if len(name) > 80:
            raise ValueError("name exceeds 80 characters")
        if requirement_type not in _REQUIREMENT_TYPES:
            raise ValueError(f"requirement_type must be one of {sorted(_REQUIREMENT_TYPES)}")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip(),
            work_item_type=work_item_type,
            requirement_type=requirement_type,
            default_dimension=default_dimension,
            default_description=default_description,
            is_mandatory=is_mandatory,
            active=active,
            created_at=now,
            updated_at=now,
        )

    def deactivate(self) -> None:
        self.active = False
        self.updated_at = datetime.now(UTC)
