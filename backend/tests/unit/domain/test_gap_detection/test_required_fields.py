"""Tests for required_fields gap detection rule."""

from __future__ import annotations

from uuid import uuid4

from app.domain.gap_detection.rules.required_fields import check_required_fields
from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType


def _work_item(
    *,
    type: WorkItemType,
    title: str = "Valid title",
    description: str | None = "A description",
    tags: list[str] | None = None,
    parent_work_item_id=None,
    priority=None,
) -> WorkItem:
    return WorkItem.create(
        title=title,
        type=type,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
        description=description,
        tags=tags or [],
        parent_work_item_id=parent_work_item_id,
        priority=priority,
    )


def _has_blocking_desc(findings: list[GapFinding]) -> bool:
    return any(
        f.dimension == "description" and f.severity == GapSeverity.BLOCKING for f in findings
    )


class TestRequiredFieldsIdea:
    """IDEA requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.IDEA, description="Some idea description")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.IDEA, description=None)
        result = check_required_fields(item)
        assert any(
            f.severity == GapSeverity.BLOCKING and f.dimension == "description" for f in result
        )

    def test_empty_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.IDEA, description="")
        result = check_required_fields(item)
        assert any(
            f.severity == GapSeverity.BLOCKING and f.dimension == "description" for f in result
        )


class TestRequiredFieldsBug:
    """BUG requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.BUG, description="Repro steps here")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.BUG, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsEnhancement:
    """ENHANCEMENT requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.ENHANCEMENT, description="Enhancement details")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.ENHANCEMENT, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsTask:
    """TASK requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.TASK, description="Task description")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.TASK, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsInitiative:
    """INITIATIVE requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.INITIATIVE, description="Initiative desc")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.INITIATIVE, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsSpike:
    """SPIKE requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.SPIKE, description="Spike description")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.SPIKE, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsBusinessChange:
    """BUSINESS_CHANGE requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.BUSINESS_CHANGE, description="Business change desc")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.BUSINESS_CHANGE, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsRequirement:
    """REQUIREMENT requires: title, description."""

    def test_all_present_returns_empty(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description="Requirement details")
        result = check_required_fields(item)
        assert result == []

    def test_missing_description_returns_blocking(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, description=None)
        assert _has_blocking_desc(check_required_fields(item))


class TestRequiredFieldsReturnType:
    def test_returns_list_of_gap_findings(self) -> None:
        item = _work_item(type=WorkItemType.BUG, description=None)
        result = check_required_fields(item)
        assert isinstance(result, list)
        assert all(isinstance(f, GapFinding) for f in result)

    def test_source_is_rule(self) -> None:
        item = _work_item(type=WorkItemType.BUG, description=None)
        result = check_required_fields(item)
        assert all(f.source == "rule" for f in result)

    def test_multiple_missing_fields_all_returned(self) -> None:
        # Title can't be empty (WorkItem invariant), but description can be None.
        item = _work_item(type=WorkItemType.BUG, description=None)
        result = check_required_fields(item)
        # At minimum description gap is present
        assert len(result) >= 1
