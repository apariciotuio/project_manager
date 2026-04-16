"""DeleteWorkItemCommand — immutable command for soft-deleting a work item."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class DeleteWorkItemCommand:
    item_id: UUID
    workspace_id: UUID
    actor_id: UUID
