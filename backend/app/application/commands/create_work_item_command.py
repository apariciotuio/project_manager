"""CreateWorkItemCommand — immutable command for creating a work item."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from app.domain.value_objects.priority import Priority
from app.domain.value_objects.work_item_type import WorkItemType


@dataclass(frozen=True, slots=True)
class CreateWorkItemCommand:
    title: str
    type: WorkItemType
    workspace_id: UUID
    project_id: UUID
    creator_id: UUID
    owner_id: UUID | None = None  # defaults to creator_id in the service
    description: str | None = None
    original_input: str | None = None
    priority: Priority | None = None
    due_date: date | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    template_id: UUID | None = None  # EP-02: audit reference, immutable after set
    parent_work_item_id: UUID | None = None  # EP-14: hierarchy link (epic > story > task)
