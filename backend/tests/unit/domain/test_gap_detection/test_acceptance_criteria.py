"""Tests for acceptance_criteria gap detection rule."""

from __future__ import annotations

from uuid import uuid4

from app.domain.gap_detection.rules.acceptance_criteria import check_acceptance_criteria
from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType


def _work_item(
    *,
    type: WorkItemType,
    description: str | None = None,
    title: str = "Valid title",
) -> WorkItem:
    return WorkItem.create(
        title=title,
        type=type,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
        description=description,
    )


# Types that require WHEN/THEN: REQUIREMENT, BUSINESS_CHANGE, ENHANCEMENT, BUG, INITIATIVE, IDEA
APPLICABLE_TYPES = [
    WorkItemType.REQUIREMENT,
    WorkItemType.BUSINESS_CHANGE,
    WorkItemType.ENHANCEMENT,
    WorkItemType.BUG,
    WorkItemType.INITIATIVE,
    WorkItemType.IDEA,
]

# Exempt: TASK, SPIKE
EXEMPT_TYPES = [WorkItemType.TASK, WorkItemType.SPIKE]


class TestApplicableTypesWithWhenThen:
    def test_requirement_with_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description="WHEN the user clicks submit THEN the form is saved",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_business_change_with_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.BUSINESS_CHANGE,
            description="WHEN a policy is cancelled THEN a refund is issued",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_enhancement_with_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.ENHANCEMENT,
            description="WHEN the user sorts by date THEN items are ordered descending",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_bug_with_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.BUG,
            description="WHEN the page loads THEN no 500 error appears",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_when_then_lowercase_accepted(self) -> None:
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description="when the user logs in then they see the dashboard",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_multiple_when_then_pairs_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description=("WHEN condition A THEN result A\nAND WHEN condition B THEN result B"),
        )
        result = check_acceptance_criteria(item)
        assert result == []


class TestApplicableTypesMissingWhenThen:
    def test_requirement_without_when_then_returns_blocking(self) -> None:
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description="The system must allow users to log in.",
        )
        result = check_acceptance_criteria(item)
        assert any(
            f.severity == GapSeverity.BLOCKING and f.dimension == "acceptance_criteria"
            for f in result
        )

    def test_business_change_without_when_then_returns_blocking(self) -> None:
        item = _work_item(
            type=WorkItemType.BUSINESS_CHANGE,
            description="We need to change the cancellation flow.",
        )
        result = check_acceptance_criteria(item)
        assert any(
            f.severity == GapSeverity.BLOCKING and f.dimension == "acceptance_criteria"
            for f in result
        )

    def test_enhancement_without_when_then_returns_blocking(self) -> None:
        item = _work_item(
            type=WorkItemType.ENHANCEMENT,
            description="Improve the UI of the dashboard.",
        )
        result = check_acceptance_criteria(item)
        assert any(f.severity == GapSeverity.BLOCKING for f in result)

    def test_no_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description=None)
        result = check_acceptance_criteria(item)
        assert any(
            f.severity == GapSeverity.BLOCKING and f.dimension == "acceptance_criteria"
            for f in result
        )

    def test_empty_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description="")
        result = check_acceptance_criteria(item)
        assert any(f.severity == GapSeverity.BLOCKING for f in result)


class TestExemptTypes:
    def test_task_without_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.TASK,
            description="Refactor the login controller.",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_spike_without_when_then_no_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.SPIKE,
            description="Investigate whether Kafka fits our use case.",
        )
        result = check_acceptance_criteria(item)
        assert result == []

    def test_task_with_no_description_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.TASK, description=None)
        result = check_acceptance_criteria(item)
        assert result == []

    def test_spike_with_no_description_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.SPIKE, description=None)
        result = check_acceptance_criteria(item)
        assert result == []


class TestAcceptanceCriteriaReturnType:
    def test_returns_list_of_gap_findings(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description="no pattern")
        result = check_acceptance_criteria(item)
        assert isinstance(result, list)
        assert all(isinstance(f, GapFinding) for f in result)

    def test_source_is_rule(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description="no pattern")
        result = check_acceptance_criteria(item)
        assert all(f.source == "rule" for f in result)
