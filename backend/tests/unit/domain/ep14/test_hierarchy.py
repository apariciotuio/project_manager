"""EP-14 — Hierarchy types + parent-child compatibility rules."""
from __future__ import annotations

import pytest

from app.domain.value_objects.work_item_type import HIERARCHY_RULES, WorkItemType


def test_milestone_and_story_exist() -> None:
    assert WorkItemType.MILESTONE == "milestone"
    assert WorkItemType.STORY == "story"


def test_ten_types_total() -> None:
    assert len(WorkItemType) == 10


@pytest.mark.parametrize(
    "parent,child,allowed",
    [
        (WorkItemType.MILESTONE, WorkItemType.STORY, True),
        (WorkItemType.MILESTONE, WorkItemType.INITIATIVE, True),
        (WorkItemType.MILESTONE, WorkItemType.BUG, False),
        (WorkItemType.STORY, WorkItemType.TASK, True),
        (WorkItemType.STORY, WorkItemType.BUG, True),
        (WorkItemType.STORY, WorkItemType.INITIATIVE, False),
        (WorkItemType.INITIATIVE, WorkItemType.STORY, True),
        (WorkItemType.INITIATIVE, WorkItemType.TASK, True),
        (WorkItemType.INITIATIVE, WorkItemType.MILESTONE, False),
        # EP-24 — idea as parent of research work
        (WorkItemType.IDEA, WorkItemType.SPIKE, True),
        (WorkItemType.IDEA, WorkItemType.TASK, True),
        (WorkItemType.IDEA, WorkItemType.BUG, False),
        (WorkItemType.IDEA, WorkItemType.INITIATIVE, False),
        # EP-24 — business_change as strategic container
        (WorkItemType.BUSINESS_CHANGE, WorkItemType.INITIATIVE, True),
        (WorkItemType.BUSINESS_CHANGE, WorkItemType.STORY, True),
        (WorkItemType.BUSINESS_CHANGE, WorkItemType.ENHANCEMENT, True),
        (WorkItemType.BUSINESS_CHANGE, WorkItemType.REQUIREMENT, False),
        (WorkItemType.BUSINESS_CHANGE, WorkItemType.TASK, False),
    ],
)
def test_hierarchy_rule_enforcement(
    parent: WorkItemType, child: WorkItemType, allowed: bool
) -> None:
    parent_rules = HIERARCHY_RULES.get(parent, set())
    assert (child in parent_rules) is allowed, (
        f"expected {parent.value} -> {child.value} to be "
        f"{'allowed' if allowed else 'forbidden'}"
    )


def test_types_without_hierarchy_rules_cannot_parent() -> None:
    """Pure leaves — cannot be parents. EP-24 promotes IDEA + BUSINESS_CHANGE
    out of this set; they become container roots."""
    types_with_no_rules = {t for t in WorkItemType if t not in HIERARCHY_RULES}
    assert WorkItemType.TASK in types_with_no_rules
    assert WorkItemType.BUG in types_with_no_rules
    assert WorkItemType.SPIKE in types_with_no_rules
    assert WorkItemType.REQUIREMENT in types_with_no_rules
    assert WorkItemType.ENHANCEMENT in types_with_no_rules
    # EP-24: IDEA and BUSINESS_CHANGE are now parents, not leaves
    assert WorkItemType.IDEA not in types_with_no_rules
    assert WorkItemType.BUSINESS_CHANGE not in types_with_no_rules
