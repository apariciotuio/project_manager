"""EP-17 — LockUnlockRequest domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

LockUnlockResponse = Literal["accepted", "declined"]


class AlreadyRespondedError(Exception):
    """Raised when the request has already been responded to."""


class CannotRequestOwnLockError(Exception):
    """Raised when the requester is the lock holder."""


@dataclass
class LockUnlockRequest:
    id: UUID
    section_id: UUID
    requester_id: UUID
    reason: str
    created_at: datetime
    responded_at: datetime | None
    response: LockUnlockResponse | None
    response_note: str | None

    def is_responded(self) -> bool:
        return self.response is not None

    def accept(self) -> None:
        if self.is_responded():
            raise AlreadyRespondedError("Request already responded to.")
        self.response = "accepted"
        self.responded_at = datetime.now(UTC)

    def decline(self, note: str | None = None) -> None:
        if self.is_responded():
            raise AlreadyRespondedError("Request already responded to.")
        self.response = "declined"
        self.response_note = note
        self.responded_at = datetime.now(UTC)

    @classmethod
    def create(
        cls,
        *,
        section_id: UUID,
        requester_id: UUID,
        reason: str,
    ) -> LockUnlockRequest:
        return cls(
            id=uuid4(),
            section_id=section_id,
            requester_id=requester_id,
            reason=reason,
            created_at=datetime.now(UTC),
            responded_at=None,
            response=None,
            response_note=None,
        )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "section_id": str(self.section_id),
            "requester_id": str(self.requester_id),
            "reason": self.reason,
            "created_at": self.created_at.isoformat(),
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "response": self.response,
            "response_note": self.response_note,
        }
