"""Acceptance criteria gap detection rule.

Types that require WHEN/THEN pattern in their description:
  REQUIREMENT, BUSINESS_CHANGE, ENHANCEMENT, BUG, INITIATIVE, IDEA

Exempt: TASK, SPIKE (they never require formal acceptance criteria).
"""
from __future__ import annotations

import re

from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType

_APPLICABLE_TYPES = frozenset(
    {
        WorkItemType.REQUIREMENT,
        WorkItemType.BUSINESS_CHANGE,
        WorkItemType.ENHANCEMENT,
        WorkItemType.BUG,
        WorkItemType.INITIATIVE,
        WorkItemType.IDEA,
    }
)

_WHEN_THEN_RE = re.compile(r"\bwhen\b.+\bthen\b", re.IGNORECASE | re.DOTALL)


def check_acceptance_criteria(work_item: WorkItem) -> list[GapFinding]:
    """Return blocking GapFinding if WHEN/THEN pattern is absent for applicable types."""
    if work_item.type not in _APPLICABLE_TYPES:
        return []

    description = work_item.description or ""
    if _WHEN_THEN_RE.search(description):
        return []

    return [
        GapFinding(
            dimension="acceptance_criteria",
            severity=GapSeverity.BLOCKING,
            message=(
                f"{work_item.type.value.replace('_', ' ').title()} work items must include "
                "at least one WHEN/THEN acceptance criterion in the description."
            ),
            source="rule",
        )
    ]
