"""Tests for GapDetector.detect()."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.gap_detection.gap_detector import GapDetector
from app.domain.models.gap_finding import GapReport, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType


def _work_item(
    *,
    type: WorkItemType = WorkItemType.TASK,
    description: str | None = "A description long enough to be valid and not trigger gaps here.",
    parent_work_item_id=None,
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


class TestGapDetectorDetect:
    def test_returns_gap_report(self) -> None:
        item = _work_item(parent_work_item_id=uuid4())
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert isinstance(report, GapReport)
        assert report.work_item_id == item.id

    def test_clean_item_returns_empty_findings_and_score_1(self) -> None:
        item = _work_item(
            type=WorkItemType.TASK,
            description="A description long enough to be valid and not trigger any gap rules here.",
            parent_work_item_id=uuid4(),
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert report.findings == []
        assert report.score == pytest.approx(1.0)

    def test_blocking_finding_reduces_score_by_0_2(self) -> None:
        # TASK without description → 1 blocking gap
        item = _work_item(type=WorkItemType.TASK, description=None, parent_work_item_id=uuid4())
        detector = GapDetector()
        report = detector.detect(item, children=[])
        blocking = sum(1 for f in report.findings if f.severity == GapSeverity.BLOCKING)
        assert blocking >= 1
        assert report.score == pytest.approx(max(0.0, 1.0 - blocking * 0.2))

    def test_warning_finding_reduces_score_by_0_05(self) -> None:
        # TASK with short description → warning only (1 warning gap expected)
        item = _work_item(
            type=WorkItemType.TASK,
            description="short",
            parent_work_item_id=uuid4(),
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        warnings = sum(1 for f in report.findings if f.severity == GapSeverity.WARNING)
        blocking = sum(1 for f in report.findings if f.severity == GapSeverity.BLOCKING)
        expected = max(0.0, 1.0 - blocking * 0.2 - warnings * 0.05)
        assert report.score == pytest.approx(expected)

    def test_score_clamped_at_zero(self) -> None:
        # Many blocking gaps → score never goes below 0
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description=None,
            parent_work_item_id=None,
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert report.score >= 0.0

    def test_score_never_exceeds_1(self) -> None:
        item = _work_item(
            type=WorkItemType.TASK,
            description="A perfectly fine description that is long enough to pass all checks here.",
            parent_work_item_id=uuid4(),
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert report.score <= 1.0

    def test_deduplicates_same_dimension_severity(self) -> None:
        """If two rules emit the same (dimension, severity), only one is kept."""
        item = _work_item(type=WorkItemType.TASK, description=None, parent_work_item_id=uuid4())
        detector = GapDetector()
        report = detector.detect(item, children=[])
        seen: set[tuple[str, GapSeverity]] = set()
        for f in report.findings:
            key = (f.dimension, f.severity)
            assert key not in seen, f"Duplicate (dimension, severity): {key}"
            seen.add(key)

    def test_blocking_sorted_before_warning(self) -> None:
        item = _work_item(
            type=WorkItemType.REQUIREMENT,
            description="short",
            parent_work_item_id=None,
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        if len(report.findings) > 1:
            severities = [f.severity for f in report.findings]
            # All blocking should appear before all warnings
            last_blocking = max(
                (i for i, s in enumerate(severities) if s == GapSeverity.BLOCKING),
                default=-1,
            )
            first_warning = min(
                (i for i, s in enumerate(severities) if s == GapSeverity.WARNING),
                default=len(severities),
            )
            assert last_blocking < first_warning

    def test_initiative_no_children_gap_included(self) -> None:
        item = _work_item(
            type=WorkItemType.INITIATIVE,
            description="A description long enough to be valid and not trigger gaps here now.",
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert any(f.dimension == "children" for f in report.findings)

    def test_initiative_with_children_no_children_gap(self) -> None:
        item = _work_item(
            type=WorkItemType.INITIATIVE,
            description="A description long enough to be valid and not trigger gaps here now.",
        )
        child = WorkItem.create(
            title="Child item",
            type=WorkItemType.REQUIREMENT,
            owner_id=uuid4(),
            creator_id=uuid4(),
            project_id=uuid4(),
            parent_work_item_id=item.id,
        )
        detector = GapDetector()
        report = detector.detect(item, children=[child])
        assert not any(f.dimension == "children" for f in report.findings)


class TestGapDetectorScoreFormula:
    def test_5_blocking_score_is_zero(self) -> None:
        """5 blocking * 0.2 = 1.0, so score = 0."""
        item = _work_item(type=WorkItemType.TASK, description=None)
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert report.score >= 0.0

    def test_zero_gaps_score_is_one(self) -> None:
        item = _work_item(
            type=WorkItemType.TASK,
            description="A perfectly adequate description with more than fifty characters total.",
            parent_work_item_id=uuid4(),
        )
        detector = GapDetector()
        report = detector.detect(item, children=[])
        assert report.score == pytest.approx(1.0)
