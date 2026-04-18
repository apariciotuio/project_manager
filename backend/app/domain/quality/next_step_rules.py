"""EP-04 Phase 6 — NextStep decision tree.

Pure functions. No I/O. First matching rule wins.

Rules (in priority order):
  1. owner=None → assign_owner
  2. completeness_score < 30 → improve_content
  3. blocking gaps present → fill_blocking_gaps
  4. state=draft + completeness >= 30 → submit_for_clarification
  5. state=in_clarification + all required sections filled → submit_for_review
  6. warning gaps present → address_warnings
  7. no validators assigned → assign_validators
  8. state=ready → export_or_wait
  9. state=exported → None (terminal)
  10. fallback → complete_specification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.quality.dimension_result import CompletenessResult
from app.domain.value_objects.work_item_state import WorkItemState


@dataclass(frozen=True)
class NextStepResult:
    next_step: str | None
    message: str
    blocking: bool
    gaps_referenced: list[str] = field(default_factory=list)
    suggested_validators: list[dict[str, Any]] = field(default_factory=list)


class _WorkItemLike:
    """Protocol-style minimal interface required by the decision tree."""

    owner_id: object
    state: WorkItemState


def evaluate(
    work_item: Any,
    completeness: CompletenessResult,
    gaps: list[dict[str, Any]],
) -> NextStepResult:
    """Evaluate next-step rules in priority order. First match wins.

    Parameters
    ----------
    work_item:
        Must have `.owner_id` (UUID | None) and `.state` (WorkItemState).
    completeness:
        Output of `ScoreCalculator.compute()` — has `.score` and `.dimensions`.
    gaps:
        Output of `GapService.list()` — list of dicts with `dimension`, `severity`, `message`.
    """
    blocking_gaps = [g for g in gaps if g.get("severity") == "blocking"]
    warning_gaps = [g for g in gaps if g.get("severity") == "warning"]
    blocking_dim_names = [g["dimension"] for g in blocking_gaps]

    # 1. No owner assigned
    if work_item.owner_id is None:
        return NextStepResult(
            next_step="assign_owner",
            message="Assign an owner before proceeding.",
            blocking=True,
        )

    # 2. Score critically low
    if completeness.score < 30:
        return NextStepResult(
            next_step="improve_content",
            message=(
                f"Completeness is {completeness.score}%. "
                "Fill in the basic sections to reach at least 30%."
            ),
            blocking=True,
        )

    # 3. Blocking gaps
    if blocking_gaps:
        return NextStepResult(
            next_step="fill_blocking_gaps",
            message=(
                f"There are {len(blocking_gaps)} blocking gap(s) that must be resolved "
                "before this item can advance."
            ),
            blocking=True,
            gaps_referenced=blocking_dim_names,
        )

    # 4. draft + score adequate → ask for clarification
    if work_item.state == WorkItemState.DRAFT:
        return NextStepResult(
            next_step="submit_for_clarification",
            message=(
                "The item looks good enough for an initial review. "
                "Submit it for clarification to gather stakeholder feedback."
            ),
            blocking=False,
        )

    # 5. in_clarification + required sections filled → submit for review
    if work_item.state == WorkItemState.IN_CLARIFICATION:
        required_unfilled = [
            d
            for d in completeness.dimensions
            if getattr(d, "applicable", True) and d.filled is False
        ]
        if not required_unfilled:
            return NextStepResult(
                next_step="submit_for_review",
                message="All sections are filled. Submit the item for formal review.",
                blocking=False,
            )
        return NextStepResult(
            next_step="fill_blocking_gaps",
            message="Resolve the remaining gaps before submitting for review.",
            blocking=True,
            gaps_referenced=[d.dimension for d in required_unfilled],
        )

    # 6. Warning gaps
    if warning_gaps:
        return NextStepResult(
            next_step="address_warnings",
            message=(
                f"There are {len(warning_gaps)} warning(s) that should be resolved "
                "to improve quality."
            ),
            blocking=False,
            gaps_referenced=[g["dimension"] for g in warning_gaps],
        )

    # 7. No validators
    # We check via the presence of a dedicated checker result or treat as gap
    validators_dim = next(
        (d for d in completeness.dimensions if d.dimension == "validations"),
        None,
    )
    if validators_dim is not None and validators_dim.applicable and not validators_dim.filled:
        return NextStepResult(
            next_step="assign_validators",
            message="Assign at least one validator to proceed.",
            blocking=False,
        )

    # 8. Terminal: ready
    if work_item.state == WorkItemState.READY:
        return NextStepResult(
            next_step="export_or_wait",
            message="The item is ready. Export it to your project management tool.",
            blocking=False,
        )

    # 9. Terminal: exported
    if work_item.state == WorkItemState.EXPORTED:
        return NextStepResult(
            next_step=None,
            message="This item has been exported to Jira.",
            blocking=False,
        )

    # 10. Fallback
    return NextStepResult(
        next_step="complete_specification",
        message="Continue improving the specification to reach full completeness.",
        blocking=False,
    )
