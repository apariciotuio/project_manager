"""EP-17 — SectionLock domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

DEFAULT_LOCK_TTL_SECONDS = 30


class LockConflictError(Exception):
    """Raised when attempting to acquire a lock held by another user."""


class LockNotFoundError(Exception):
    pass


@dataclass
class SectionLock:
    id: UUID
    section_id: UUID
    work_item_id: UUID
    held_by: UUID
    acquired_at: datetime
    heartbeat_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        t = now or datetime.now(UTC)
        return t >= self.expires_at

    def heartbeat(self, ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS) -> None:
        now = datetime.now(UTC)
        self.heartbeat_at = now
        self.expires_at = now + timedelta(seconds=ttl_seconds)

    def release(self, user_id: UUID) -> None:
        """Release the lock; raises LockConflictError if not owned by user_id."""
        if self.held_by != user_id:
            raise LockConflictError(f"Lock held by {self.held_by}, cannot be released by {user_id}")

    def force_release(self) -> None:
        """Admin override — no ownership check."""

    @classmethod
    def acquire(
        cls,
        *,
        section_id: UUID,
        work_item_id: UUID,
        held_by: UUID,
        ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    ) -> SectionLock:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            section_id=section_id,
            work_item_id=work_item_id,
            held_by=held_by,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
