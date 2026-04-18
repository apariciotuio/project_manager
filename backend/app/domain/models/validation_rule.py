"""ValidationRule domain entity — EP-10 admin rules."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

Enforcement = Literal["required", "recommended", "blocked_override"]
_VALID_ENFORCEMENTS: frozenset[str] = frozenset({"required", "recommended", "blocked_override"})


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ValidationRule:
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    work_item_type: str
    validation_type: str
    enforcement: Enforcement
    active: bool
    created_by: UUID
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    # Computed annotation fields (not persisted — set by precedence service)
    effective: bool = True
    superseded_by: UUID | None = None

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        project_id: UUID | None,
        work_item_type: str,
        validation_type: str,
        enforcement: str,
        created_by: UUID,
    ) -> ValidationRule:
        if not work_item_type.strip():
            raise ValueError("work_item_type must not be empty")
        if not validation_type.strip():
            raise ValueError("validation_type must not be empty")
        if enforcement not in _VALID_ENFORCEMENTS:
            raise ValueError(f"enforcement must be one of {sorted(_VALID_ENFORCEMENTS)}")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            work_item_type=work_item_type,
            validation_type=validation_type,
            enforcement=enforcement,  # type: ignore[arg-type]
            active=True,
            created_by=created_by,
        )

    def update(
        self,
        *,
        enforcement: str | None = None,
        active: bool | None = None,
    ) -> None:
        if enforcement is not None:
            if enforcement not in _VALID_ENFORCEMENTS:
                raise ValueError(f"enforcement must be one of {sorted(_VALID_ENFORCEMENTS)}")
            self.enforcement = enforcement  # type: ignore[assignment]
        if active is not None:
            self.active = active
        self.updated_at = _now()

    def deactivate(self) -> None:
        self.active = False
        self.updated_at = _now()

    def is_workspace_scope(self) -> bool:
        return self.project_id is None

    def is_global_blocker(self) -> bool:
        return self.is_workspace_scope() and self.enforcement == "blocked_override"
