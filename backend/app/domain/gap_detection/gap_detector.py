"""GapDetector — orchestrates all rule functions and returns a GapReport."""

from __future__ import annotations

from app.domain.gap_detection.rules.acceptance_criteria import check_acceptance_criteria
from app.domain.gap_detection.rules.content_quality import check_content_quality
from app.domain.gap_detection.rules.hierarchy_rules import check_hierarchy_rules
from app.domain.gap_detection.rules.required_fields import check_required_fields
from app.domain.models.gap_finding import GapFinding, GapReport, GapSeverity
from app.domain.models.work_item import WorkItem

_SEVERITY_ORDER: dict[GapSeverity, int] = {
    GapSeverity.BLOCKING: 0,
    GapSeverity.INFO: 1,
    GapSeverity.WARNING: 2,
}


class GapDetector:
    """Runs all rule functions, deduplicates, sorts, and scores."""

    def detect(
        self,
        work_item: WorkItem,
        children: list[WorkItem] | None = None,
    ) -> GapReport:
        """Run all rules and return a deduplicated, sorted GapReport.

        Args:
            work_item: The work item to evaluate.
            children: Direct children of this work item (used by hierarchy rule).
                      Pass [] when children are unknown/not loaded; hierarchy
                      rule will emit a warning for Initiatives.
        """
        raw: list[GapFinding] = []
        raw.extend(check_required_fields(work_item))
        raw.extend(check_content_quality(work_item))
        raw.extend(check_acceptance_criteria(work_item))
        raw.extend(check_hierarchy_rules(work_item, children if children is not None else []))

        deduplicated = _deduplicate(raw)
        sorted_findings = sorted(deduplicated, key=lambda f: _SEVERITY_ORDER[f.severity])
        score = _compute_score(sorted_findings)

        return GapReport(
            work_item_id=work_item.id,
            findings=sorted_findings,
            score=score,
        )


def _deduplicate(findings: list[GapFinding]) -> list[GapFinding]:
    """Keep only the first finding per (dimension, severity) pair."""
    seen: set[tuple[str, GapSeverity]] = set()
    result: list[GapFinding] = []
    for f in findings:
        key = (f.dimension, f.severity)
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def _compute_score(findings: list[GapFinding]) -> float:
    hard = sum(1 for f in findings if f.severity == GapSeverity.BLOCKING)
    soft = sum(1 for f in findings if f.severity == GapSeverity.WARNING)
    raw = 1.0 - (hard * 0.2 + soft * 0.05)
    return max(0.0, min(1.0, raw))
