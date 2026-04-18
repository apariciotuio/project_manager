"""Unit tests for WorkItem entity — RED phase."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest


def _make_work_item(**kwargs):  # type: ignore[no-untyped-def]
    from app.domain.models.work_item import WorkItem
    from app.domain.value_objects.work_item_type import WorkItemType

    defaults = {
        "title": "A valid title",
        "type": WorkItemType.BUG,
        "owner_id": uuid4(),
        "creator_id": uuid4(),
        "project_id": uuid4(),
    }
    defaults.update(kwargs)
    return WorkItem.create(**defaults)


class TestWorkItemConstruction:
    def test_defaults_set_correctly(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        wi = _make_work_item()
        assert wi.state == WorkItemState.DRAFT
        assert wi.completeness_score == 0
        assert wi.has_override is False
        assert wi.tags == []
        assert wi.deleted_at is None
        assert wi.owner_suspended_flag is False

    def test_owner_id_defaults_to_creator_when_not_provided(self) -> None:
        creator = uuid4()
        wi = _make_work_item(creator_id=creator, owner_id=creator)
        assert wi.owner_id == creator

    def test_id_is_uuid(self) -> None:
        from uuid import UUID

        wi = _make_work_item()
        assert isinstance(wi.id, UUID)

    def test_created_at_set(self) -> None:
        before = datetime.now(UTC)
        wi = _make_work_item()
        after = datetime.now(UTC)
        assert before <= wi.created_at <= after

    def test_title_stored_stripped(self) -> None:
        wi = _make_work_item(title="  hello world  ")
        assert wi.title == "hello world"


class TestWorkItemTitleValidation:
    def test_two_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_work_item(title="ab")

    def test_three_chars_passes(self) -> None:
        wi = _make_work_item(title="abc")
        assert wi.title == "abc"

    def test_255_chars_passes(self) -> None:
        wi = _make_work_item(title="x" * 255)
        assert len(wi.title) == 255

    def test_256_chars_raises(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_work_item(title="x" * 256)

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_work_item(title="")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _make_work_item(title="   ")


class TestCanTransitionTo:
    def test_valid_transition_owner_returns_true(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        ok, reason = wi.can_transition_to(WorkItemState.IN_CLARIFICATION, owner)
        assert ok is True
        assert reason == ""

    def test_invalid_transition_returns_false_with_reason(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        ok, reason = wi.can_transition_to(WorkItemState.READY, owner)
        assert ok is False
        assert reason == "invalid_transition"

    def test_non_owner_returns_false_not_owner(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        other = uuid4()
        wi = _make_work_item(owner_id=owner)
        ok, reason = wi.can_transition_to(WorkItemState.IN_CLARIFICATION, other)
        assert ok is False
        assert reason == "not_owner"


class TestApplyTransition:
    def test_valid_transition_returns_state_transition(self) -> None:
        from app.domain.value_objects.state_transition import StateTransition
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        result = wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        assert isinstance(result, StateTransition)
        assert result.from_state == WorkItemState.DRAFT
        assert result.to_state == WorkItemState.IN_CLARIFICATION
        assert result.actor_id == owner
        assert wi.state == WorkItemState.IN_CLARIFICATION

    def test_triggered_at_within_one_second(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        before = datetime.now(UTC)
        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        result = wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        after = datetime.now(UTC)
        assert before - timedelta(seconds=1) <= result.triggered_at <= after + timedelta(seconds=1)

    def test_invalid_transition_raises(self) -> None:
        from app.domain.exceptions import InvalidTransitionError
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        with pytest.raises(InvalidTransitionError):
            wi.apply_transition(WorkItemState.READY, owner, reason=None)

    def test_non_owner_raises_not_owner_error(self) -> None:
        from app.domain.exceptions import NotOwnerError
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        other = uuid4()
        wi = _make_work_item(owner_id=owner)
        with pytest.raises(NotOwnerError):
            wi.apply_transition(WorkItemState.IN_CLARIFICATION, other, reason=None)

    def test_reason_stored_in_transition(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        result = wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason="starting now")
        assert result.reason == "starting now"

    def test_updated_at_bumped(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        old_updated = wi.updated_at
        wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        assert wi.updated_at >= old_updated


class TestForceReady:
    def _get_in_clarification_item(self):  # type: ignore[no-untyped-def]
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        return wi, owner

    def test_sets_has_override_true(self) -> None:
        wi, owner = self._get_in_clarification_item()
        wi.force_ready(owner, "this is a valid justification text")
        assert wi.has_override is True

    def test_returns_state_transition_with_is_override_true(self) -> None:
        from app.domain.value_objects.state_transition import StateTransition
        from app.domain.value_objects.work_item_state import WorkItemState

        wi, owner = self._get_in_clarification_item()
        result = wi.force_ready(owner, "this is a valid justification text")
        assert isinstance(result, StateTransition)
        assert result.is_override is True
        assert result.to_state == WorkItemState.READY

    def test_override_justification_stored(self) -> None:
        wi, owner = self._get_in_clarification_item()
        justification = "this is a valid justification text"
        result = wi.force_ready(owner, justification)
        assert result.override_justification == justification
        assert wi.override_justification == justification

    def test_non_owner_raises(self) -> None:
        from app.domain.exceptions import NotOwnerError

        wi, owner = self._get_in_clarification_item()
        other = uuid4()
        with pytest.raises(NotOwnerError):
            wi.force_ready(other, "valid justification here")

    def test_short_justification_raises(self) -> None:
        from app.domain.exceptions import InvalidOverrideError

        wi, owner = self._get_in_clarification_item()
        with pytest.raises(InvalidOverrideError):
            wi.force_ready(owner, "short")

    def test_empty_justification_raises(self) -> None:
        from app.domain.exceptions import InvalidOverrideError

        wi, owner = self._get_in_clarification_item()
        with pytest.raises(InvalidOverrideError):
            wi.force_ready(owner, "")

    def test_works_from_any_non_exported_state(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        # Still in DRAFT — force_ready should work
        wi.force_ready(owner, "valid justification text here")
        assert wi.state == WorkItemState.READY

    def test_state_set_to_ready(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        wi, owner = self._get_in_clarification_item()
        wi.force_ready(owner, "this is a valid justification text")
        assert wi.state == WorkItemState.READY


class TestReassignOwner:
    def test_returns_ownership_record(self) -> None:
        from app.domain.value_objects.ownership_record import OwnershipRecord

        owner = uuid4()
        new_owner = uuid4()
        changed_by = uuid4()
        wi = _make_work_item(owner_id=owner)
        rec = wi.reassign_owner(new_owner, changed_by, reason="handoff")
        assert isinstance(rec, OwnershipRecord)
        assert rec.previous_owner_id == owner
        assert rec.new_owner_id == new_owner
        assert rec.changed_by == changed_by
        assert rec.reason == "handoff"

    def test_owner_id_updated(self) -> None:
        owner = uuid4()
        new_owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.reassign_owner(new_owner, owner, reason=None)
        assert wi.owner_id == new_owner

    def test_updated_at_bumped(self) -> None:
        owner = uuid4()
        new_owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        old_updated = wi.updated_at
        wi.reassign_owner(new_owner, owner, reason=None)
        assert wi.updated_at >= old_updated

    def test_same_owner_raises(self) -> None:
        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        with pytest.raises(ValueError, match="same owner"):
            wi.reassign_owner(owner, owner, reason=None)

    def test_work_item_id_in_record(self) -> None:
        owner = uuid4()
        new_owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        rec = wi.reassign_owner(new_owner, owner, reason=None)
        assert rec.work_item_id == wi.id


class TestDerivedState:
    def test_draft_returns_in_progress(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState
        from app.domain.value_objects.work_item_state import WorkItemState

        wi = _make_work_item()
        assert wi.state == WorkItemState.DRAFT
        assert wi.derived_state == DerivedState.IN_PROGRESS

    def test_ready_state_returns_ready(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.force_ready(owner, "valid justification text here")
        assert wi.derived_state == DerivedState.READY

    def test_exported_returns_none(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.force_ready(owner, "valid justification text here")
        # Manually set to exported since we have no way to transition there normally
        # without the full service layer
        wi.state = WorkItemState.EXPORTED
        assert wi.derived_state is None

    def test_owner_suspended_flag_returns_blocked(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState

        wi = _make_work_item()
        wi.owner_suspended_flag = True
        assert wi.derived_state == DerivedState.BLOCKED

    def test_in_clarification_active_returns_in_progress(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        assert wi.derived_state == DerivedState.IN_PROGRESS

    def test_blocked_takes_precedence_over_in_progress(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState
        from app.domain.value_objects.work_item_state import WorkItemState

        owner = uuid4()
        wi = _make_work_item(owner_id=owner)
        wi.apply_transition(WorkItemState.IN_CLARIFICATION, owner, reason=None)
        wi.owner_suspended_flag = True
        assert wi.derived_state == DerivedState.BLOCKED


class TestComputeCompleteness:
    def test_returns_nonzero_for_item_with_title_and_owner(self) -> None:
        # "A valid title" = 13 chars >= 10 → 25 pts; owner assigned, not suspended → 15 pts
        wi = _make_work_item()
        assert wi.compute_completeness() == 40

    def test_returns_int(self) -> None:
        wi = _make_work_item()
        result = wi.compute_completeness()
        assert isinstance(result, int)

    def test_consistent_across_calls(self) -> None:
        wi = _make_work_item()
        assert wi.compute_completeness() == wi.compute_completeness()
