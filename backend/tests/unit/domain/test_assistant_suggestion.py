"""Unit tests for AssistantSuggestion entity — RED phase."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.exceptions import InvalidSuggestionStateError, SuggestionExpiredError
from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus

_NOW = datetime(2026, 4, 16, 12, 0, 0, tzinfo=UTC)
_FUTURE = _NOW + timedelta(hours=24)
_PAST = _NOW - timedelta(seconds=1)


def _make(
    status: SuggestionStatus = SuggestionStatus.PENDING,
    expires_at: datetime = _FUTURE,
) -> AssistantSuggestion:
    return AssistantSuggestion(
        id=uuid4(),
        work_item_id=uuid4(),
        thread_id=None,
        section_id=None,
        proposed_content="proposed text",
        current_content="current text",
        rationale="because reasons",
        status=status,
        version_number_target=1,
        batch_id=uuid4(),
        dundun_request_id="req-123",
        created_by=uuid4(),
        created_at=_NOW,
        updated_at=_NOW,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# accept()
# ---------------------------------------------------------------------------


class TestAccept:
    def test_pending_suggestion_can_be_accepted(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        result = suggestion.accept(_NOW)
        assert result.status == SuggestionStatus.ACCEPTED

    def test_accept_returns_new_instance(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        result = suggestion.accept(_NOW)
        assert result is not suggestion

    def test_accept_updates_updated_at(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        later = _NOW + timedelta(minutes=5)
        result = suggestion.accept(later)
        assert result.updated_at == later

    def test_accept_preserves_other_fields(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        result = suggestion.accept(_NOW)
        assert result.id == suggestion.id
        assert result.proposed_content == suggestion.proposed_content
        assert result.batch_id == suggestion.batch_id

    def test_accept_expired_suggestion_raises(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING, expires_at=_PAST)
        with pytest.raises(SuggestionExpiredError) as exc_info:
            suggestion.accept(_NOW)
        assert exc_info.value.suggestion_id == suggestion.id

    def test_accept_already_accepted_raises(self) -> None:
        suggestion = _make(SuggestionStatus.ACCEPTED)
        with pytest.raises(InvalidSuggestionStateError) as exc_info:
            suggestion.accept(_NOW)
        assert exc_info.value.suggestion_id == suggestion.id
        assert exc_info.value.current_status == SuggestionStatus.ACCEPTED
        assert exc_info.value.attempted_transition == "accept"

    def test_accept_rejected_suggestion_raises(self) -> None:
        suggestion = _make(SuggestionStatus.REJECTED)
        with pytest.raises(InvalidSuggestionStateError):
            suggestion.accept(_NOW)

    def test_accept_status_expired_raises_expired_error(self) -> None:
        """Status=expired (set externally) also prevents accept."""
        suggestion = _make(SuggestionStatus.EXPIRED)
        with pytest.raises(SuggestionExpiredError):
            suggestion.accept(_NOW)


# ---------------------------------------------------------------------------
# reject()
# ---------------------------------------------------------------------------


class TestReject:
    def test_pending_suggestion_can_be_rejected(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        result = suggestion.reject(_NOW)
        assert result.status == SuggestionStatus.REJECTED

    def test_reject_returns_new_instance(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        result = suggestion.reject(_NOW)
        assert result is not suggestion

    def test_reject_updates_updated_at(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING)
        later = _NOW + timedelta(minutes=3)
        result = suggestion.reject(later)
        assert result.updated_at == later

    def test_reject_accepted_suggestion_raises(self) -> None:
        suggestion = _make(SuggestionStatus.ACCEPTED)
        with pytest.raises(InvalidSuggestionStateError) as exc_info:
            suggestion.reject(_NOW)
        assert exc_info.value.attempted_transition == "reject"

    def test_reject_rejected_suggestion_raises(self) -> None:
        suggestion = _make(SuggestionStatus.REJECTED)
        with pytest.raises(InvalidSuggestionStateError):
            suggestion.reject(_NOW)

    def test_reject_expired_status_raises_invalid_state(self) -> None:
        suggestion = _make(SuggestionStatus.EXPIRED)
        with pytest.raises(InvalidSuggestionStateError):
            suggestion.reject(_NOW)


# ---------------------------------------------------------------------------
# is_expired()
# ---------------------------------------------------------------------------


class TestIsExpired:
    def test_not_expired_when_expires_at_in_future(self) -> None:
        suggestion = _make(expires_at=_FUTURE)
        assert suggestion.is_expired(_NOW) is False

    def test_expired_when_expires_at_in_past(self) -> None:
        suggestion = _make(expires_at=_PAST)
        assert suggestion.is_expired(_NOW) is True

    def test_expired_when_expires_at_equals_now(self) -> None:
        """Boundary: expires_at == now is NOT yet expired (strictly less than)."""
        suggestion = _make(expires_at=_NOW)
        assert suggestion.is_expired(_NOW) is False

    def test_expired_when_status_is_expired(self) -> None:
        suggestion = _make(SuggestionStatus.EXPIRED, expires_at=_FUTURE)
        assert suggestion.is_expired(_NOW) is True

    def test_not_expired_when_pending_and_future(self) -> None:
        suggestion = _make(SuggestionStatus.PENDING, expires_at=_FUTURE)
        assert suggestion.is_expired(_NOW) is False
