"""WorkItemType — the 10 supported work item types.

EP-01 base: idea, bug, enhancement, task, initiative, spike, business_change, requirement.
EP-14 extensions: milestone, story (hierarchy types).
"""
from __future__ import annotations

from enum import StrEnum


class WorkItemType(StrEnum):
    IDEA = "idea"
    BUG = "bug"
    ENHANCEMENT = "enhancement"
    TASK = "task"
    INITIATIVE = "initiative"
    SPIKE = "spike"
    BUSINESS_CHANGE = "business_change"
    REQUIREMENT = "requirement"
    # EP-14 hierarchy types
    MILESTONE = "milestone"
    STORY = "story"


# Parent-child type compatibility rules (EP-14).
# key = parent type, value = allowed child types.
HIERARCHY_RULES: dict[WorkItemType, set[WorkItemType]] = {
    WorkItemType.MILESTONE: {
        WorkItemType.INITIATIVE,
        WorkItemType.STORY,
        WorkItemType.ENHANCEMENT,
    },
    WorkItemType.INITIATIVE: {
        WorkItemType.STORY,
        WorkItemType.REQUIREMENT,
        WorkItemType.ENHANCEMENT,
        WorkItemType.BUG,
        WorkItemType.TASK,
    },
    WorkItemType.STORY: {
        WorkItemType.TASK,
        WorkItemType.BUG,
        WorkItemType.SPIKE,
    },
}
