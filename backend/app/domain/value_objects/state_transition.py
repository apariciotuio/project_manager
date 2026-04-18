"""StateTransition — immutable record of a single FSM state change."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.work_item_state import WorkItemState


@dataclass(frozen=True)
class StateTransition:
    work_item_id: UUID
    from_state: WorkItemState
    to_state: WorkItemState
    actor_id: UUID | None  # None when actor is the system (migration 0010 makes DB column nullable)
    triggered_at: datetime
    reason: str | None
    is_override: bool
    override_justification: str | None
