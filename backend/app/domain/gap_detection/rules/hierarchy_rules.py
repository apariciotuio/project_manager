"""Hierarchy gap detection rule.

Design decision: `check_hierarchy_rules` takes an extra `children` parameter
because determining whether an Initiative has children requires external state
that cannot be derived from the WorkItem entity alone. Passing `children` keeps
the function pure (no I/O) while handling the Initiative case cleanly.
The caller (GapDetector / ClarificationService) is responsible for providing
the children list; in unit tests it is passed as a fake list.

Rules:
- INITIATIVE without children → warning (gap on dimension "children")
- TASK / REQUIREMENT / ENHANCEMENT without parent_work_item_id → warning (dimension "parent")
"""
from __future__ import annotations

from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType

_REQUIRES_PARENT = frozenset(
    {
        WorkItemType.TASK,
        WorkItemType.REQUIREMENT,
        WorkItemType.ENHANCEMENT,
    }
)


def check_hierarchy_rules(
    work_item: WorkItem,
    children: list[WorkItem],
) -> list[GapFinding]:
    """Return warning GapFindings for hierarchy violations.

    Args:
        work_item: The work item to evaluate.
        children: Direct children of this work item (may be empty list).
    """
    findings: list[GapFinding] = []

    if work_item.type == WorkItemType.INITIATIVE and not children:
        findings.append(
            GapFinding(
                dimension="children",
                severity=GapSeverity.WARNING,
                message=(
                    "Initiative has no linked child work items. "
                    "Add requirements or enhancements to decompose the initiative."
                ),
                source="rule",
            )
        )

    if work_item.type in _REQUIRES_PARENT and work_item.parent_work_item_id is None:
        findings.append(
            GapFinding(
                dimension="parent",
                severity=GapSeverity.WARNING,
                message=(
                    f"{work_item.type.value.replace('_', ' ').title()} work items should "
                    "be linked to a parent work item."
                ),
                source="rule",
            )
        )

    return findings
