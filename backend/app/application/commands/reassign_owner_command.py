"""ReassignOwnerCommand — immutable command for ownership reassignment."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ReassignOwnerCommand:
    item_id: UUID
    workspace_id: UUID
    actor_id: UUID
    new_owner_id: UUID
    reason: str | None = None
