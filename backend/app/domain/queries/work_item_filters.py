"""WorkItemFilters — frozen query parameters for listing work items."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType


@dataclass(frozen=True)
class WorkItemFilters:
    state: WorkItemState | None = None
    type: WorkItemType | None = None
    owner_id: UUID | None = None
    has_override: bool | None = None
    include_deleted: bool = False
    page: int = 1
    page_size: int = 50
