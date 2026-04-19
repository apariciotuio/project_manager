"""WorkItemType — the 10 supported work item types.

EP-01 base: idea, bug, enhancement, task, initiative, spike, business_change, requirement.
EP-14 extensions: milestone, story (hierarchy types).
EP-24 extensions: idea + business_change admitted as parent types (discovery /
strategic containers). See `HIERARCHY_RULES` below.
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


# Parent-child type compatibility rules (EP-14, extended by EP-24).
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
    # EP-24 — IDEA as discovery container (research work only)
    WorkItemType.IDEA: {
        WorkItemType.SPIKE,
        WorkItemType.TASK,
    },
    # EP-24 — BUSINESS_CHANGE as strategic container (epic-like, non-temporal)
    WorkItemType.BUSINESS_CHANGE: {
        WorkItemType.INITIATIVE,
        WorkItemType.STORY,
        WorkItemType.ENHANCEMENT,
    },
}
