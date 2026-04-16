"""Tests for hierarchy_rules gap detection rule."""
from __future__ import annotations

from uuid import uuid4

from app.domain.gap_detection.rules.hierarchy_rules import check_hierarchy_rules
from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType


def _work_item(
    *,
    type: WorkItemType,
    parent_work_item_id=None,
    description: str | None = "Some description here.",
    title: str = "Valid title",
) -> WorkItem:
    return WorkItem.create(
        title=title,
        type=type,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
        description=description,
        parent_work_item_id=parent_work_item_id,
    )


def _child(*, type: WorkItemType, parent_id) -> WorkItem:
    return _work_item(type=type, parent_work_item_id=parent_id)


class TestInitiativeWithoutChildren:
    def test_initiative_no_children_returns_gap(self) -> None:
        item = _work_item(type=WorkItemType.INITIATIVE)
        result = check_hierarchy_rules(item, children=[])
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "children"
            for f in result
        )

    def test_initiative_with_children_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.INITIATIVE)
        child = _child(type=WorkItemType.REQUIREMENT, parent_id=item.id)
        result = check_hierarchy_rules(item, children=[child])
        assert result == []

    def test_initiative_with_multiple_children_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.INITIATIVE)
        children = [
            _child(type=WorkItemType.REQUIREMENT, parent_id=item.id),
            _child(type=WorkItemType.ENHANCEMENT, parent_id=item.id),
        ]
        result = check_hierarchy_rules(item, children=children)
        assert result == []


class TestTaskWithoutParent:
    def test_task_without_parent_returns_warning(self) -> None:
        item = _work_item(type=WorkItemType.TASK, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "parent"
            for f in result
        )

    def test_task_with_parent_no_gap(self) -> None:
        parent_id = uuid4()
        item = _work_item(type=WorkItemType.TASK, parent_work_item_id=parent_id)
        result = check_hierarchy_rules(item, children=[])
        assert result == []


class TestRequirementWithoutParent:
    def test_requirement_without_parent_returns_warning(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert any(f.severity == GapSeverity.WARNING and f.dimension == "parent" for f in result)

    def test_requirement_with_parent_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.REQUIREMENT, parent_work_item_id=uuid4())
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)


class TestEnhancementWithoutParent:
    def test_enhancement_without_parent_returns_warning(self) -> None:
        item = _work_item(type=WorkItemType.ENHANCEMENT, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert any(f.severity == GapSeverity.WARNING and f.dimension == "parent" for f in result)

    def test_enhancement_with_parent_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.ENHANCEMENT, parent_work_item_id=uuid4())
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)


class TestTypesWithNoHierarchyRequirement:
    """IDEA, SPIKE, BUSINESS_CHANGE don't require a parent."""

    def test_idea_without_parent_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.IDEA, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)

    def test_spike_without_parent_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.SPIKE, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)

    def test_business_change_without_parent_no_gap(self) -> None:
        item = _work_item(type=WorkItemType.BUSINESS_CHANGE, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)

    def test_bug_without_parent_no_gap(self) -> None:
        """Bugs can be standalone."""
        item = _work_item(type=WorkItemType.BUG, parent_work_item_id=None)
        result = check_hierarchy_rules(item, children=[])
        assert not any(f.dimension == "parent" for f in result)


class TestHierarchyRulesReturnType:
    def test_returns_list_of_gap_findings(self) -> None:
        item = _work_item(type=WorkItemType.TASK)
        result = check_hierarchy_rules(item, children=[])
        assert isinstance(result, list)
        assert all(isinstance(f, GapFinding) for f in result)

    def test_source_is_rule(self) -> None:
        item = _work_item(type=WorkItemType.TASK)
        result = check_hierarchy_rules(item, children=[])
        assert all(f.source == "rule" for f in result)
