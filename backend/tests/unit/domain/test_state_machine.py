"""Unit tests for WorkItem state machine — RED phase."""
from __future__ import annotations

import pytest

VALID_TRANSITIONS_EXPECTED = [
    ("draft", "in_clarification"),
    ("in_clarification", "in_review"),
    ("in_clarification", "changes_requested"),
    ("in_clarification", "partially_validated"),
    ("in_clarification", "ready"),
    ("in_review", "changes_requested"),
    ("in_review", "partially_validated"),
    ("in_review", "in_clarification"),
    ("changes_requested", "in_clarification"),
    ("changes_requested", "in_review"),
    ("partially_validated", "in_review"),
    ("partially_validated", "ready"),
    ("ready", "exported"),
    ("ready", "in_clarification"),
]

INVALID_TRANSITIONS_EXPECTED = [
    ("draft", "in_review"),
    ("draft", "ready"),
    ("draft", "exported"),
    ("in_clarification", "exported"),
    ("in_review", "exported"),
    ("changes_requested", "ready"),
    ("changes_requested", "exported"),
    ("partially_validated", "exported"),
    ("exported", "draft"),
    ("exported", "in_clarification"),
    ("exported", "in_review"),
    ("exported", "changes_requested"),
    ("exported", "partially_validated"),
    ("exported", "ready"),
]


class TestValidTransitionsCount:
    def test_exactly_fourteen_valid_edges(self) -> None:
        from app.domain.state_machine import VALID_TRANSITIONS

        assert len(VALID_TRANSITIONS) == 14


@pytest.mark.parametrize("from_s,to_s", VALID_TRANSITIONS_EXPECTED)
def test_valid_transition_returns_true(from_s: str, to_s: str) -> None:
    from app.domain.state_machine import is_valid_transition
    from app.domain.value_objects.work_item_state import WorkItemState

    assert is_valid_transition(WorkItemState(from_s), WorkItemState(to_s)) is True


@pytest.mark.parametrize("from_s,to_s", INVALID_TRANSITIONS_EXPECTED)
def test_invalid_transition_returns_false(from_s: str, to_s: str) -> None:
    from app.domain.state_machine import is_valid_transition
    from app.domain.value_objects.work_item_state import WorkItemState

    assert is_valid_transition(WorkItemState(from_s), WorkItemState(to_s)) is False


class TestExplicitRejections:
    """Acceptance criteria explicit cases."""

    def test_draft_to_ready_invalid(self) -> None:
        from app.domain.state_machine import is_valid_transition
        from app.domain.value_objects.work_item_state import WorkItemState

        assert is_valid_transition(WorkItemState.DRAFT, WorkItemState.READY) is False

    def test_exported_to_draft_invalid(self) -> None:
        from app.domain.state_machine import is_valid_transition
        from app.domain.value_objects.work_item_state import WorkItemState

        assert is_valid_transition(WorkItemState.EXPORTED, WorkItemState.DRAFT) is False

    def test_changes_requested_to_ready_invalid(self) -> None:
        from app.domain.state_machine import is_valid_transition
        from app.domain.value_objects.work_item_state import WorkItemState

        assert (
            is_valid_transition(WorkItemState.CHANGES_REQUESTED, WorkItemState.READY) is False
        )

    def test_exported_is_terminal_no_outbound(self) -> None:
        """Exported has zero outbound edges."""
        from app.domain.state_machine import VALID_TRANSITIONS
        from app.domain.value_objects.work_item_state import WorkItemState

        outbound = [(f, t) for f, t in VALID_TRANSITIONS if f == WorkItemState.EXPORTED]
        assert outbound == []
