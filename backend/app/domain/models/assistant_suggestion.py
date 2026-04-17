"""AssistantSuggestion domain entity and SuggestionBatch value object — pure, no I/O."""
from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID

from app.domain.exceptions import InvalidSuggestionStateError, SuggestionExpiredError


class SuggestionStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"


_TERMINAL = frozenset({SuggestionStatus.ACCEPTED, SuggestionStatus.REJECTED})


def _now() -> datetime:
    return datetime.now(UTC)


@dataclasses.dataclass
class AssistantSuggestion:
    id: UUID
    workspace_id: UUID
    work_item_id: UUID
    thread_id: UUID | None
    section_id: UUID | None
    proposed_content: str
    current_content: str
    rationale: str | None
    status: SuggestionStatus
    version_number_target: int
    batch_id: UUID
    dundun_request_id: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime) -> bool:
        return self.status == SuggestionStatus.EXPIRED or self.expires_at < now

    def accept(self, now: datetime) -> AssistantSuggestion:
        if self.status == SuggestionStatus.EXPIRED or self.expires_at < now:
            raise SuggestionExpiredError(self.id)
        if self.status != SuggestionStatus.PENDING:
            raise InvalidSuggestionStateError(self.id, self.status, "accept")
        return dataclasses.replace(self, status=SuggestionStatus.ACCEPTED, updated_at=now)

    def reject(self, now: datetime) -> AssistantSuggestion:
        if self.status != SuggestionStatus.PENDING:
            raise InvalidSuggestionStateError(self.id, self.status, "reject")
        return dataclasses.replace(self, status=SuggestionStatus.REJECTED, updated_at=now)


class SuggestionBatch:
    """Derived, non-persisted value object computed from a list of suggestions."""

    def __init__(self, suggestions: list[AssistantSuggestion], now: datetime) -> None:
        if not suggestions:
            raise ValueError("SuggestionBatch requires at least one suggestion")
        batch_ids = {s.batch_id for s in suggestions}
        if len(batch_ids) > 1:
            raise ValueError(f"All suggestions must share the same batch_id; got {batch_ids}")
        self._suggestions = suggestions
        self._now = now
        self.batch_id: UUID = suggestions[0].batch_id

    @property
    def status(self) -> str:
        has_expired = any(s.is_expired(self._now) for s in self._suggestions)
        if has_expired:
            return "expired"
        statuses = {s.status for s in self._suggestions}
        all_terminal = statuses <= _TERMINAL
        if all_terminal:
            return "fully_applied"
        if statuses == {SuggestionStatus.PENDING}:
            return "pending"
        return "partially_applied"
