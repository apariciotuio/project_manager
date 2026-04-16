"""Content quality gap detection rule.

Checks:
- Description shorter than MIN_DESCRIPTION_LENGTH → warning
- Description is only a vague placeholder (TBD / TODO / N/A alone) → warning
"""
from __future__ import annotations

import re

from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem

MIN_DESCRIPTION_LENGTH = 50

# Vague-only pattern: the entire stripped description is nothing but the placeholder
_VAGUE_ONLY_RE = re.compile(r"^(tbd|todo|n/a)$", re.IGNORECASE)


def check_content_quality(work_item: WorkItem) -> list[GapFinding]:
    """Return warning GapFindings for low-quality content."""
    description = work_item.description
    if not description:
        # None or empty string — required_fields handles the hard gap; nothing to check here
        return []

    stripped = description.strip()
    if not stripped:
        return []

    findings: list[GapFinding] = []

    if _VAGUE_ONLY_RE.match(stripped):
        findings.append(
            GapFinding(
                dimension="description",
                severity=GapSeverity.WARNING,
                message=(
                    f"Description appears to be a placeholder ({stripped.upper()}). "
                    "Replace with meaningful content."
                ),
                source="rule",
            )
        )
        # A pure placeholder is also short, but we don't double-report the same dimension+severity
        return findings

    if len(stripped) < MIN_DESCRIPTION_LENGTH:
        findings.append(
            GapFinding(
                dimension="description",
                severity=GapSeverity.WARNING,
                message=(
                    f"Description is too short ({len(stripped)} chars). "
                    f"Aim for at least {MIN_DESCRIPTION_LENGTH} characters."
                ),
                source="rule",
            )
        )

    return findings
