"""EP-04 — Validator entity.

Tracks a single role validation request on a work item. UNIQUE(work_item_id, role).
responded_at is set by the service when status transitions from PENDING.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ValidatorStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    DECLINED = "declined"


@dataclass
class Validator:
    id: UUID
    work_item_id: UUID
    user_id: UUID | None
    role: str
    status: ValidatorStatus
    assigned_at: datetime
    assigned_by: UUID
    responded_at: datetime | None
    workspace_id: UUID | None = None

    def respond(self, new_status: ValidatorStatus) -> None:
        if new_status is ValidatorStatus.PENDING:
            raise ValueError("cannot transition back to pending")
        if self.status is not ValidatorStatus.PENDING:
            raise ValueError(f"already responded (status={self.status.value})")
        self.status = new_status
        self.responded_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        role: str,
        assigned_by: UUID,
        user_id: UUID | None = None,
    ) -> Validator:
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            user_id=user_id,
            role=role,
            status=ValidatorStatus.PENDING,
            assigned_at=datetime.now(UTC),
            assigned_by=assigned_by,
            responded_at=None,
        )
