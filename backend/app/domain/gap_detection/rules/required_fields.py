"""Required fields gap detection rule.

Each WorkItemType has required fields. Missing or empty required fields
emit a GapFinding with severity=BLOCKING.
"""

from __future__ import annotations

from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem

# All types require title (enforced by WorkItem invariant) and description.
# Extend this mapping when new fields are added to WorkItem.
_REQUIRED_FIELDS_BY_TYPE: dict[str, list[str]] = {
    "idea": ["description"],
    "bug": ["description"],
    "enhancement": ["description"],
    "task": ["description"],
    "initiative": ["description"],
    "spike": ["description"],
    "business_change": ["description"],
    "requirement": ["description"],
}


def check_required_fields(work_item: WorkItem) -> list[GapFinding]:
    """Return blocking GapFindings for each missing required field."""
    required = _REQUIRED_FIELDS_BY_TYPE.get(work_item.type.value, [])
    findings: list[GapFinding] = []

    for field in required:
        value = getattr(work_item, field, None)
        if not value:  # None or empty string
            findings.append(
                GapFinding(
                    dimension=field,
                    severity=GapSeverity.BLOCKING,
                    message=f"'{field}' is required for {work_item.type.value} work items.",
                    source="rule",
                )
            )

    return findings
