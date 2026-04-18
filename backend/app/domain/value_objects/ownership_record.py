"""OwnershipRecord — immutable record of a single ownership transfer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class OwnershipRecord:
    work_item_id: UUID
    previous_owner_id: UUID
    new_owner_id: UUID
    changed_by: UUID
    changed_at: datetime
    reason: str | None
