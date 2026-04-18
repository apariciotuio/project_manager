"""EP-04 Phase 6 — NextStep decision tree unit tests.

One test per rule. Rules are tested in isolation by controlling inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.quality.dimension_result import CompletenessResult, DimensionResult
from app.domain.quality.next_step_rules import evaluate
from app.domain.value_objects.work_item_state import WorkItemState


@dataclass
class _WI:
    owner_id: UUID | None
    state: WorkItemState = WorkItemState.DRAFT


def _completeness(score: int = 80, dims: list[DimensionResult] | None = None) -> CompletenessResult:
    return CompletenessResult(
        score=score,
        level="high" if score >= 70 else ("medium" if score >= 40 else "low"),
        dimensions=dims or [],
    )


def _gap(dimension: str, severity: str = "blocking") -> dict:
    return {"dimension": dimension, "severity": severity, "message": f"{dimension} gap"}


# ---------------------------------------------------------------------------
# Rule 1: no owner → assign_owner
# ---------------------------------------------------------------------------


class TestAssignOwnerRule:
    def test_no_owner_returns_assign_owner(self) -> None:
        wi = _WI(owner_id=None)
        result = evaluate(wi, _completeness(80), [])
        assert result.next_step == "assign_owner"
        assert result.blocking is True

    def test_owner_present_skips_rule(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.EXPORTED)
        result = evaluate(wi, _completeness(100), [])
        # Should fall through to exported rule (next_step=None)
        assert result.next_step is None


# ---------------------------------------------------------------------------
# Rule 2: score < 30 → improve_content
# ---------------------------------------------------------------------------


class TestImproveContentRule:
    def test_score_below_30_returns_improve_content(self) -> None:
        wi = _WI(owner_id=uuid4())
        result = evaluate(wi, _completeness(15), [])
        assert result.next_step == "improve_content"
        assert result.blocking is True

    def test_score_exactly_30_skips_rule(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.EXPORTED)
        result = evaluate(wi, _completeness(30), [])
        assert result.next_step != "improve_content"

    def test_score_0_still_improve_content(self) -> None:
        wi = _WI(owner_id=uuid4())
        result = evaluate(wi, _completeness(0), [])
        assert result.next_step == "improve_content"


# ---------------------------------------------------------------------------
# Rule 3: blocking gaps → fill_blocking_gaps
# ---------------------------------------------------------------------------


class TestFillBlockingGapsRule:
    def test_blocking_gaps_returns_fill_blocking_gaps(self) -> None:
        wi = _WI(owner_id=uuid4())
        gaps = [_gap("acceptance_criteria", "blocking")]
        result = evaluate(wi, _completeness(50), gaps)
        assert result.next_step == "fill_blocking_gaps"
        assert result.blocking is True
        assert "acceptance_criteria" in result.gaps_referenced

    def test_warning_only_skips_blocking_gap_rule(self) -> None:
        # Warning gaps do NOT trigger fill_blocking_gaps rule
        wi = _WI(owner_id=uuid4(), state=WorkItemState.IN_REVIEW)
        gaps = [_gap("dependencies", "warning")]
        result = evaluate(wi, _completeness(100), gaps)
        assert result.next_step != "fill_blocking_gaps"


# ---------------------------------------------------------------------------
# Rule 4: draft + adequate score → submit_for_clarification
# ---------------------------------------------------------------------------


class TestSubmitForClarificationRule:
    def test_draft_with_score_30_plus_returns_submit(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.DRAFT)
        result = evaluate(wi, _completeness(60), [])
        assert result.next_step == "submit_for_clarification"
        assert result.blocking is False

    def test_draft_with_all_gaps_cleared(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.DRAFT)
        result = evaluate(wi, _completeness(90), [])
        assert result.next_step == "submit_for_clarification"


# ---------------------------------------------------------------------------
# Rule 5: in_clarification → submit_for_review or fill gaps
# ---------------------------------------------------------------------------


class TestInClarificationRule:
    def test_all_filled_returns_submit_for_review(self) -> None:
        dims = [
            DimensionResult("ownership", weight=1.0, applicable=True, filled=True, score=1.0),
        ]
        wi = _WI(owner_id=uuid4(), state=WorkItemState.IN_CLARIFICATION)
        result = evaluate(wi, _completeness(100, dims), [])
        assert result.next_step == "submit_for_review"

    def test_unfilled_dims_returns_fill_gaps(self) -> None:
        dims = [
            DimensionResult(
                "acceptance_criteria", weight=0.22, applicable=True, filled=False, score=0.0
            ),
        ]
        wi = _WI(owner_id=uuid4(), state=WorkItemState.IN_CLARIFICATION)
        result = evaluate(wi, _completeness(30, dims), [])
        assert result.next_step == "fill_blocking_gaps"
        assert result.blocking is True


# ---------------------------------------------------------------------------
# Rule 6: warning gaps
# ---------------------------------------------------------------------------


class TestAddressWarningsRule:
    def test_warning_gaps_returns_address_warnings(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.IN_REVIEW)
        gaps = [_gap("dependencies", "warning")]
        result = evaluate(wi, _completeness(80), gaps)
        assert result.next_step == "address_warnings"
        assert result.blocking is False
        assert "dependencies" in result.gaps_referenced


# ---------------------------------------------------------------------------
# Rule 7: no validators → assign_validators
# ---------------------------------------------------------------------------


class TestAssignValidatorsRule:
    def test_no_validators_returns_assign_validators(self) -> None:
        dims = [
            DimensionResult(
                "validations",
                weight=0.12,
                applicable=True,
                filled=False,
                score=0.0,
                message="assign validator",
            ),
        ]
        wi = _WI(owner_id=uuid4(), state=WorkItemState.IN_REVIEW)
        result = evaluate(wi, _completeness(85, dims), [])
        assert result.next_step == "assign_validators"
        assert result.blocking is False


# ---------------------------------------------------------------------------
# Rule 8: ready → export_or_wait
# ---------------------------------------------------------------------------


class TestExportOrWaitRule:
    def test_ready_state_returns_export_or_wait(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.READY)
        result = evaluate(wi, _completeness(95), [])
        assert result.next_step == "export_or_wait"
        assert result.blocking is False


# ---------------------------------------------------------------------------
# Rule 9: exported → None (terminal)
# ---------------------------------------------------------------------------


class TestExportedTerminal:
    def test_exported_returns_null_next_step(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.EXPORTED)
        result = evaluate(wi, _completeness(100), [])
        assert result.next_step is None
        assert result.blocking is False

    def test_exported_message_references_jira(self) -> None:
        wi = _WI(owner_id=uuid4(), state=WorkItemState.EXPORTED)
        result = evaluate(wi, _completeness(100), [])
        assert "exported" in result.message.lower() or "jira" in result.message.lower()
