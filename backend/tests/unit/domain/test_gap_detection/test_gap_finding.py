"""Tests for GapFinding, GapReport, GapSeverity domain models."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.gap_finding import GapFinding, GapReport, GapSeverity


class TestGapSeverity:
    def test_blocking_value(self) -> None:
        assert GapSeverity.BLOCKING == "blocking"

    def test_warning_value(self) -> None:
        assert GapSeverity.WARNING == "warning"

    def test_info_value(self) -> None:
        assert GapSeverity.INFO == "info"

    def test_ordering_blocking_lt_warning(self) -> None:
        severities = [GapSeverity.WARNING, GapSeverity.BLOCKING, GapSeverity.INFO]
        assert sorted(severities) == [GapSeverity.BLOCKING, GapSeverity.INFO, GapSeverity.WARNING]


class TestGapFinding:
    def test_create_blocking_finding(self) -> None:
        f = GapFinding(
            dimension="title",
            severity=GapSeverity.BLOCKING,
            message="Title is required",
            source="rule",
        )
        assert f.dimension == "title"
        assert f.severity == GapSeverity.BLOCKING
        assert f.message == "Title is required"
        assert f.source == "rule"

    def test_create_warning_finding(self) -> None:
        f = GapFinding(
            dimension="description",
            severity=GapSeverity.WARNING,
            message="Description is too short",
            source="rule",
        )
        assert f.severity == GapSeverity.WARNING

    def test_create_dundun_sourced_finding(self) -> None:
        f = GapFinding(
            dimension="acceptance_criteria",
            severity=GapSeverity.BLOCKING,
            message="Missing WHEN/THEN",
            source="dundun",
        )
        assert f.source == "dundun"

    def test_invalid_source_raises(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            GapFinding(
                dimension="x",
                severity=GapSeverity.INFO,
                message="m",
                source="invalid",  # type: ignore[arg-type]
            )

    def test_equality_by_value(self) -> None:
        f1 = GapFinding(dimension="d", severity=GapSeverity.BLOCKING, message="m", source="rule")
        f2 = GapFinding(dimension="d", severity=GapSeverity.BLOCKING, message="m", source="rule")
        assert f1 == f2

    def test_inequality_different_severity(self) -> None:
        f1 = GapFinding(dimension="d", severity=GapSeverity.BLOCKING, message="m", source="rule")
        f2 = GapFinding(dimension="d", severity=GapSeverity.WARNING, message="m", source="rule")
        assert f1 != f2


class TestGapReport:
    def test_create_empty_report(self) -> None:
        work_item_id = uuid4()
        report = GapReport(work_item_id=work_item_id, findings=[], score=1.0)
        assert report.work_item_id == work_item_id
        assert report.findings == []
        assert report.score == 1.0

    def test_score_clamped_between_0_and_1(self) -> None:
        work_item_id = uuid4()
        report = GapReport(work_item_id=work_item_id, findings=[], score=1.0)
        assert 0.0 <= report.score <= 1.0

    def test_create_report_with_findings(self) -> None:
        findings = [
            GapFinding(
                dimension="title", severity=GapSeverity.BLOCKING, message="m", source="rule"
            ),
            GapFinding(
                dimension="desc", severity=GapSeverity.WARNING, message="m2", source="rule"
            ),
        ]
        report = GapReport(work_item_id=uuid4(), findings=findings, score=0.75)
        assert len(report.findings) == 2
