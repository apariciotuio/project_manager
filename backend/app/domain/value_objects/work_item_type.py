"""WorkItemType — the 8 supported work item types (EP-01).

Note: milestone and story are EP-14 extensions — do not add here.
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
