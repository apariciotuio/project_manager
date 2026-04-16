"""ForceReadyCommand — immutable command for overriding the ready gate."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ForceReadyCommand:
    item_id: UUID
    workspace_id: UUID
    actor_id: UUID
    justification: str
    confirmed: bool
