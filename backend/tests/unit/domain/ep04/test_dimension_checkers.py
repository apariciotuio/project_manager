"""EP-04 Phase 4 — dimension checker unit tests (triangulated).

Each checker gets:
  - at least 3 input variants
  - an applicable=False case
  - boundary conditions per the spec
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.validator import Validator, ValidatorStatus
from app.domain.quality import dimension_checkers as dc
from app.domain.value_objects.work_item_type import WorkItemType


@dataclass
class _WI:
    type: WorkItemType
    owner_id: UUID | None = None
    owner_suspended_flag: bool = False


def _s(kind: SectionType, content: str) -> Section:
    now = datetime.now(UTC)
    return Section(
        id=uuid4(),
        work_item_id=uuid4(),
        section_type=kind,
        content=content,
        display_order=1,
        is_required=False,
        generation_source=GenerationSource.LLM,
        version=1,
        created_at=now,
        updated_at=now,
        created_by=uuid4(),
        updated_by=uuid4(),
    )


def _v(status: ValidatorStatus = ValidatorStatus.PENDING) -> Validator:
    return Validator(
        id=uuid4(),
        work_item_id=uuid4(),
        user_id=None,
        role="r",
        status=status,
        assigned_at=datetime.now(UTC),
        assigned_by=uuid4(),
        responded_at=None,
    )


# ---------------------------------------------------------------------------
# check_problem_clarity
# ---------------------------------------------------------------------------


class TestProblemClarity:
    """WHEN/THEN from design.md + spec scenarios."""

    def test_not_applicable_for_task(self) -> None:
        r = dc.check_problem_clarity(_WI(WorkItemType.TASK), [], [])
        assert r.applicable is False
        assert r.dimension == "problem_clarity"

    def test_not_applicable_for_spike(self) -> None:
        r = dc.check_problem_clarity(_WI(WorkItemType.SPIKE), [], [])
        assert r.applicable is False

    def test_not_filled_below_threshold(self) -> None:
        wi = _WI(WorkItemType.BUG)
        # 30 chars only — below 100
        r = dc.check_problem_clarity(wi, [_s(SectionType.SUMMARY, "A" * 30)], [])
        assert r.applicable is True
        assert r.filled is False

    def test_filled_when_combined_reaches_100(self) -> None:
        wi = _WI(WorkItemType.BUG)
        sections = [
            _s(SectionType.SUMMARY, "A" * 60),
            _s(SectionType.ACTUAL_BEHAVIOR, "B" * 45),
        ]
        r = dc.check_problem_clarity(wi, sections, [])
        assert r.filled is True

    def test_context_section_used_for_non_bug(self) -> None:
        wi = _WI(WorkItemType.REQUIREMENT)
        sections = [
            _s(SectionType.SUMMARY, "S" * 50),
            _s(SectionType.CONTEXT, "C" * 55),
        ]
        r = dc.check_problem_clarity(wi, sections, [])
        assert r.filled is True

    def test_message_set_when_not_filled(self) -> None:
        r = dc.check_problem_clarity(_WI(WorkItemType.BUG), [], [])
        assert r.message is not None
        assert len(r.message) > 0


# ---------------------------------------------------------------------------
# check_objective
# ---------------------------------------------------------------------------


class TestObjective:
    def test_boundary_49_chars_not_filled(self) -> None:
        wi = _WI(WorkItemType.REQUIREMENT)
        r = dc.check_objective(wi, [_s(SectionType.OBJECTIVE, "x" * 49)], [])
        assert r.filled is False

    def test_boundary_50_chars_filled(self) -> None:
        wi = _WI(WorkItemType.REQUIREMENT)
        r = dc.check_objective(wi, [_s(SectionType.OBJECTIVE, "x" * 50)], [])
        assert r.filled is True

    def test_not_applicable_for_bug(self) -> None:
        # BUG is not in _TYPES_NEEDING_OBJECTIVE
        r = dc.check_objective(_WI(WorkItemType.BUG), [], [])
        assert r.applicable is False

    def test_empty_section_not_filled(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_objective(wi, [_s(SectionType.OBJECTIVE, "")], [])
        assert r.filled is False

    def test_message_present_when_not_filled(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_objective(wi, [], [])
        assert r.message is not None


# ---------------------------------------------------------------------------
# check_scope
# ---------------------------------------------------------------------------


class TestScope:
    def test_applicable_for_requirement(self) -> None:
        r = dc.check_scope(_WI(WorkItemType.REQUIREMENT), [_s(SectionType.SCOPE, "x" * 10)], [])
        assert r.applicable is True
        assert r.filled is True

    def test_not_applicable_for_bug(self) -> None:
        r = dc.check_scope(_WI(WorkItemType.BUG), [], [])
        assert r.applicable is False

    def test_empty_scope_not_filled(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_scope(wi, [_s(SectionType.SCOPE, "")], [])
        assert r.filled is False

    def test_whitespace_only_not_filled(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_scope(wi, [_s(SectionType.SCOPE, "   ")], [])
        assert r.filled is False


# ---------------------------------------------------------------------------
# check_acceptance_criteria
# ---------------------------------------------------------------------------


class TestAcceptanceCriteria:
    def test_one_bullet_not_enough(self) -> None:
        wi = _WI(WorkItemType.BUG)
        r = dc.check_acceptance_criteria(wi, [_s(SectionType.ACCEPTANCE_CRITERIA, "- only one")], [])
        assert r.filled is False

    def test_two_bullets_sufficient(self) -> None:
        wi = _WI(WorkItemType.BUG)
        r = dc.check_acceptance_criteria(
            wi, [_s(SectionType.ACCEPTANCE_CRITERIA, "- one\n- two")], []
        )
        assert r.filled is True

    def test_asterisk_bullets_count(self) -> None:
        wi = _WI(WorkItemType.ENHANCEMENT)
        r = dc.check_acceptance_criteria(
            wi, [_s(SectionType.ACCEPTANCE_CRITERIA, "* first\n* second")], []
        )
        assert r.filled is True

    def test_not_applicable_for_task(self) -> None:
        r = dc.check_acceptance_criteria(_WI(WorkItemType.TASK), [], [])
        assert r.applicable is False

    def test_no_section_not_filled(self) -> None:
        wi = _WI(WorkItemType.REQUIREMENT)
        r = dc.check_acceptance_criteria(wi, [], [])
        assert r.filled is False


# ---------------------------------------------------------------------------
# check_dependencies
# ---------------------------------------------------------------------------


class TestDependencies:
    @pytest.mark.parametrize("content", ["none", "None", "NONE"])
    def test_none_case_insensitive(self, content: str) -> None:
        r = dc.check_dependencies(_WI(WorkItemType.BUG), [_s(SectionType.DEPENDENCIES, content)], [])
        assert r.filled is True

    def test_empty_not_filled(self) -> None:
        r = dc.check_dependencies(_WI(WorkItemType.BUG), [_s(SectionType.DEPENDENCIES, "")], [])
        assert r.filled is False

    def test_actual_content_filled(self) -> None:
        r = dc.check_dependencies(
            _WI(WorkItemType.BUG),
            [_s(SectionType.DEPENDENCIES, "depends on auth service")],
            [],
        )
        assert r.filled is True

    def test_always_applicable(self) -> None:
        r = dc.check_dependencies(_WI(WorkItemType.TASK), [], [])
        assert r.applicable is True


# ---------------------------------------------------------------------------
# check_risks
# ---------------------------------------------------------------------------


class TestRisks:
    @pytest.mark.parametrize("content", ["none", "None"])
    def test_none_content_is_filled(self, content: str) -> None:
        r = dc.check_risks(_WI(WorkItemType.BUG), [_s(SectionType.RISKS, content)], [])
        assert r.filled is True

    def test_empty_not_filled(self) -> None:
        r = dc.check_risks(_WI(WorkItemType.BUG), [_s(SectionType.RISKS, "")], [])
        assert r.filled is False

    def test_actual_risks_filled(self) -> None:
        r = dc.check_risks(
            _WI(WorkItemType.BUG),
            [_s(SectionType.RISKS, "risk of data loss if migration fails")],
            [],
        )
        assert r.filled is True


# ---------------------------------------------------------------------------
# check_breakdown
# ---------------------------------------------------------------------------


class TestBreakdown:
    def test_applicable_for_initiative(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_breakdown(wi, [_s(SectionType.BREAKDOWN, "- child 1")], [])
        assert r.applicable is True
        assert r.filled is True

    def test_not_applicable_for_bug(self) -> None:
        r = dc.check_breakdown(_WI(WorkItemType.BUG), [], [])
        assert r.applicable is False

    def test_empty_breakdown_not_filled(self) -> None:
        wi = _WI(WorkItemType.INITIATIVE)
        r = dc.check_breakdown(wi, [_s(SectionType.BREAKDOWN, "")], [])
        assert r.filled is False

    def test_single_line_counts(self) -> None:
        wi = _WI(WorkItemType.BUSINESS_CHANGE)
        r = dc.check_breakdown(wi, [_s(SectionType.BREAKDOWN, "at least one line")], [])
        assert r.filled is True


# ---------------------------------------------------------------------------
# check_ownership
# ---------------------------------------------------------------------------


class TestOwnership:
    def test_no_owner_not_filled(self) -> None:
        r = dc.check_ownership(_WI(WorkItemType.BUG, owner_id=None), [], [])
        assert r.filled is False

    def test_suspended_owner_not_filled(self) -> None:
        r = dc.check_ownership(
            _WI(WorkItemType.BUG, owner_id=uuid4(), owner_suspended_flag=True), [], []
        )
        assert r.filled is False

    def test_active_owner_filled(self) -> None:
        r = dc.check_ownership(_WI(WorkItemType.BUG, owner_id=uuid4()), [], [])
        assert r.filled is True

    def test_always_applicable(self) -> None:
        r = dc.check_ownership(_WI(WorkItemType.TASK), [], [])
        assert r.applicable is True


# ---------------------------------------------------------------------------
# check_validations
# ---------------------------------------------------------------------------


class TestValidations:
    def test_pending_validator_fills(self) -> None:
        r = dc.check_validations(_WI(WorkItemType.BUG), [], [_v(ValidatorStatus.PENDING)])
        assert r.filled is True

    def test_approved_validator_fills(self) -> None:
        r = dc.check_validations(_WI(WorkItemType.BUG), [], [_v(ValidatorStatus.APPROVED)])
        assert r.filled is True

    def test_declined_does_not_fill(self) -> None:
        validator = _v(ValidatorStatus.PENDING)
        validator.respond(ValidatorStatus.DECLINED)
        r = dc.check_validations(_WI(WorkItemType.BUG), [], [validator])
        assert r.filled is False

    def test_empty_validators_not_filled(self) -> None:
        r = dc.check_validations(_WI(WorkItemType.BUG), [], [])
        assert r.filled is False


# ---------------------------------------------------------------------------
# check_all orchestrator
# ---------------------------------------------------------------------------


class TestCheckAll:
    def test_returns_9_results(self) -> None:
        wi = _WI(WorkItemType.BUG, owner_id=uuid4())
        results = dc.check_all(wi, [], [])
        assert len(results) == len(dc.ALL_CHECKERS)

    def test_all_dimensions_have_names(self) -> None:
        wi = _WI(WorkItemType.BUG, owner_id=uuid4())
        results = dc.check_all(wi, [], [])
        assert all(r.dimension for r in results)
