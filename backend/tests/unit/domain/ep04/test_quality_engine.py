"""EP-04 Phase 4 + 5 — dimension checkers + score calculator."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from app.domain.models.section import Section
from app.domain.models.section_type import GenerationSource, SectionType
from app.domain.models.validator import Validator, ValidatorStatus
from app.domain.quality import dimension_checkers as dc
from app.domain.quality.score_calculator import compute as compute_score
from app.domain.value_objects.work_item_type import WorkItemType


@dataclass
class _FakeWorkItem:
    type: WorkItemType
    owner_id: UUID | None = None
    owner_suspended_flag: bool = False


def _section(kind: SectionType, content: str, *, required: bool = False) -> Section:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    uid = uuid4()
    return Section(
        id=uid,
        work_item_id=uuid4(),
        section_type=kind,
        content=content,
        display_order=1,
        is_required=required,
        generation_source=GenerationSource.LLM,
        version=1,
        created_at=now,
        updated_at=now,
        created_by=uuid4(),
        updated_by=uuid4(),
    )


def _validator(status: ValidatorStatus = ValidatorStatus.PENDING) -> Validator:
    return Validator.create(
        work_item_id=uuid4(), role="product_owner", assigned_by=uuid4()
    )._replace_status(status) if False else Validator(
        id=uuid4(),
        work_item_id=uuid4(),
        user_id=None,
        role="r",
        status=status,
        assigned_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        assigned_by=uuid4(),
        responded_at=None,
    )


class TestProblemClarity:
    def test_not_applicable_for_task(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.TASK, owner_id=uuid4())
        r = dc.check_problem_clarity(wi, [], [])
        assert r.applicable is False

    def test_filled_when_combined_length_100(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        sections = [
            _section(SectionType.SUMMARY, "A" * 60),
            _section(SectionType.ACTUAL_BEHAVIOR, "B" * 45),
        ]
        r = dc.check_problem_clarity(wi, sections, [])
        assert r.filled is True

    def test_not_filled_when_combined_length_below_100(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        sections = [_section(SectionType.SUMMARY, "A" * 30)]
        r = dc.check_problem_clarity(wi, sections, [])
        assert r.filled is False


class TestObjective:
    def test_exact_boundary(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.REQUIREMENT, owner_id=uuid4())
        at_49 = [_section(SectionType.OBJECTIVE, "x" * 49)]
        at_50 = [_section(SectionType.OBJECTIVE, "x" * 50)]
        assert dc.check_objective(wi, at_49, []).filled is False
        assert dc.check_objective(wi, at_50, []).filled is True


class TestAcceptanceCriteria:
    def test_one_bullet_not_enough(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        sections = [_section(SectionType.ACCEPTANCE_CRITERIA, "- one bullet only")]
        assert dc.check_acceptance_criteria(wi, sections, []).filled is False

    def test_two_bullets_enough(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        sections = [
            _section(
                SectionType.ACCEPTANCE_CRITERIA, "- first bullet\n- second bullet"
            )
        ]
        assert dc.check_acceptance_criteria(wi, sections, []).filled is True


class TestDependencies:
    def test_none_case_insensitive(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        for content in ("none", "None", "NONE"):
            sections = [_section(SectionType.DEPENDENCIES, content)]
            assert dc.check_dependencies(wi, sections, []).filled is True


class TestOwnership:
    def test_suspended_owner_not_filled(self) -> None:
        wi = _FakeWorkItem(
            type=WorkItemType.BUG, owner_id=uuid4(), owner_suspended_flag=True
        )
        assert dc.check_ownership(wi, [], []).filled is False

    def test_no_owner_not_filled(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=None)
        assert dc.check_ownership(wi, [], []).filled is False

    def test_active_owner_filled(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        assert dc.check_ownership(wi, [], []).filled is True


class TestValidations:
    def test_pending_counts(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        assert dc.check_validations(wi, [], [_validator()]).filled is True

    def test_declined_does_not_count(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        v = _validator()
        v.respond(ValidatorStatus.DECLINED)
        assert dc.check_validations(wi, [], [v]).filled is False


class TestScoreCalculator:
    def test_all_inapplicable_returns_zero_without_crash(self) -> None:
        # Purely inapplicable dimensions must not raise ZeroDivisionError.
        dims = [
            dc._result("problem_clarity", applicable=False, filled=False),
        ]
        result = compute_score(dims)
        assert result.score == 0
        assert result.level == "low"

    def test_all_filled_gives_100(self) -> None:
        wi = _FakeWorkItem(type=WorkItemType.BUG, owner_id=uuid4())
        sections = [
            _section(SectionType.SUMMARY, "A" * 60),
            _section(SectionType.ACTUAL_BEHAVIOR, "B" * 50),
            _section(SectionType.ACCEPTANCE_CRITERIA, "- one\n- two"),
            _section(SectionType.DEPENDENCIES, "none"),
            _section(SectionType.RISKS, "none"),
        ]
        result = compute_score(dc.check_all(wi, sections, [_validator()]))
        assert result.score == 100
        assert result.level == "ready"
