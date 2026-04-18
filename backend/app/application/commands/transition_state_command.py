"""TransitionStateCommand — immutable command for FSM state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.value_objects.work_item_state import WorkItemState


@dataclass(frozen=True, slots=True)
class TransitionStateCommand:
    item_id: UUID
    workspace_id: UUID
    target_state: WorkItemState
    actor_id: UUID
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
