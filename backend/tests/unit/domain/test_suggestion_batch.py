"""Unit tests for SuggestionBatch value object — RED phase."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.models.assistant_suggestion import (
    AssistantSuggestion,
    SuggestionBatch,
    SuggestionStatus,
)

_NOW = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_FUTURE = _NOW + timedelta(hours=24)
_PAST = _NOW - timedelta(seconds=1)


def _make(
    status: SuggestionStatus = SuggestionStatus.PENDING,
    expires_at: datetime = _FUTURE,
    batch_id: object = None,
) -> AssistantSuggestion:
    from uuid import UUID
    bid: UUID = batch_id if batch_id is not None else uuid4()  # type: ignore[assignment]
    return AssistantSuggestion(
        id=uuid4(),
        work_item_id=uuid4(),
        thread_id=None,
        section_id=None,
        proposed_content="proposed",
        current_content="current",
        rationale=None,
        status=status,
        version_number_target=1,
        batch_id=bid,
        dundun_request_id=None,
        created_by=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# Batch status derivation
# ---------------------------------------------------------------------------


class TestSuggestionBatchStatus:
    def test_all_pending_returns_pending(self) -> None:
        bid = uuid4()
        suggestions = [_make(SuggestionStatus.PENDING, batch_id=bid) for _ in range(3)]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "pending"

    def test_all_accepted_returns_fully_applied(self) -> None:
        bid = uuid4()
        suggestions = [_make(SuggestionStatus.ACCEPTED, batch_id=bid) for _ in range(2)]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "fully_applied"

    def test_all_rejected_returns_fully_applied(self) -> None:
        bid = uuid4()
        suggestions = [_make(SuggestionStatus.REJECTED, batch_id=bid) for _ in range(2)]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "fully_applied"

    def test_mixed_accepted_rejected_returns_fully_applied(self) -> None:
        bid = uuid4()
        suggestions = [
            _make(SuggestionStatus.ACCEPTED, batch_id=bid),
            _make(SuggestionStatus.REJECTED, batch_id=bid),
        ]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "fully_applied"

    def test_mixed_pending_and_terminal_returns_partially_applied(self) -> None:
        bid = uuid4()
        suggestions = [
            _make(SuggestionStatus.PENDING, batch_id=bid),
            _make(SuggestionStatus.ACCEPTED, batch_id=bid),
        ]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "partially_applied"

    def test_pending_with_expired_status_returns_expired(self) -> None:
        bid = uuid4()
        suggestions = [
            _make(SuggestionStatus.PENDING, batch_id=bid),
            _make(SuggestionStatus.EXPIRED, batch_id=bid),
        ]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "expired"

    def test_pending_with_past_expires_at_returns_expired(self) -> None:
        bid = uuid4()
        suggestions = [
            _make(SuggestionStatus.PENDING, expires_at=_FUTURE, batch_id=bid),
            _make(SuggestionStatus.PENDING, expires_at=_PAST, batch_id=bid),
        ]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.status == "expired"

    def test_single_pending_suggestion_returns_pending(self) -> None:
        bid = uuid4()
        batch = SuggestionBatch([_make(SuggestionStatus.PENDING, batch_id=bid)], _NOW)
        assert batch.status == "pending"

    def test_single_accepted_suggestion_returns_fully_applied(self) -> None:
        bid = uuid4()
        batch = SuggestionBatch([_make(SuggestionStatus.ACCEPTED, batch_id=bid)], _NOW)
        assert batch.status == "fully_applied"


# ---------------------------------------------------------------------------
# batch_id
# ---------------------------------------------------------------------------


class TestSuggestionBatchId:
    def test_batch_id_taken_from_suggestions(self) -> None:
        bid = uuid4()
        suggestions = [_make(SuggestionStatus.PENDING, batch_id=bid) for _ in range(2)]
        batch = SuggestionBatch(suggestions, _NOW)
        assert batch.batch_id == bid

    def test_mixed_batch_ids_raises_value_error(self) -> None:
        s1 = _make(batch_id=uuid4())
        s2 = _make(batch_id=uuid4())
        with pytest.raises(ValueError, match="batch_id"):
            SuggestionBatch([s1, s2], _NOW)

    def test_empty_list_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            SuggestionBatch([], _NOW)
