"""UpdateWorkItemCommand — immutable command for partial field updates.

# state is NOT updatable here — use TransitionStateCommand
# owner_id, workspace_id, project_id are also excluded (immutable post-creation
# or have dedicated commands).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.value_objects.priority import Priority


@dataclass(frozen=True, slots=True)
class UpdateWorkItemCommand:
    item_id: UUID
    workspace_id: UUID
    actor_id: UUID
    title: str | None = None
    description: str | None = None
    original_input: str | None = None
    priority: Priority | None = None
    due_date: date | None = None
    tags: tuple[str, ...] | None = None  # None = not changing; empty tuple = clear tags
