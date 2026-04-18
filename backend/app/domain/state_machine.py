"""WorkItem state machine — pure graph membership check, zero business logic."""

from __future__ import annotations

from app.domain.value_objects.work_item_state import WorkItemState

_S = WorkItemState

VALID_TRANSITIONS: frozenset[tuple[WorkItemState, WorkItemState]] = frozenset(
    {
        (_S.DRAFT, _S.IN_CLARIFICATION),
        (_S.IN_CLARIFICATION, _S.IN_REVIEW),
        (_S.IN_CLARIFICATION, _S.CHANGES_REQUESTED),
        (_S.IN_CLARIFICATION, _S.PARTIALLY_VALIDATED),
        (_S.IN_CLARIFICATION, _S.READY),
        (_S.IN_REVIEW, _S.CHANGES_REQUESTED),
        (_S.IN_REVIEW, _S.PARTIALLY_VALIDATED),
        (_S.IN_REVIEW, _S.IN_CLARIFICATION),
        (_S.CHANGES_REQUESTED, _S.IN_CLARIFICATION),
        (_S.CHANGES_REQUESTED, _S.IN_REVIEW),
        (_S.PARTIALLY_VALIDATED, _S.IN_REVIEW),
        (_S.PARTIALLY_VALIDATED, _S.READY),
        (_S.READY, _S.EXPORTED),
        (_S.READY, _S.IN_CLARIFICATION),
    }
)


def is_valid_transition(from_state: WorkItemState, to_state: WorkItemState) -> bool:
    return (from_state, to_state) in VALID_TRANSITIONS
