"""EP-07 Phase 3 — DiffService unit tests."""
from __future__ import annotations

import time

import pytest

from app.application.services.diff_service import DiffService, SectionChangeType


def _snap(work_item: dict, sections: list[dict]) -> dict:
    return {
        "schema_version": 1,
        "work_item": work_item,
        "sections": sections,
        "task_node_ids": [],
    }


def _section(section_type: str, content: str, order: int = 0) -> dict:
    return {"section_id": "uuid", "section_type": section_type, "content": content, "order": order}


class TestComputeVersionDiff:
    def test_identical_snapshots_all_unchanged(self) -> None:
        svc = DiffService()
        s = _snap({"title": "T", "state": "draft"}, [_section("problem", "same")])
        result = svc.compute_version_diff(s, s)
        assert all(sec["change_type"] == SectionChangeType.UNCHANGED for sec in result["sections"])
        assert result["metadata_diff"]["title"] is None
        assert result["metadata_diff"]["state"] is None

    def test_title_change_in_metadata(self) -> None:
        svc = DiffService()
        a = _snap({"title": "Old", "state": "draft"}, [])
        b = _snap({"title": "New", "state": "draft"}, [])
        result = svc.compute_version_diff(a, b)
        assert result["metadata_diff"]["title"] == {"before": "Old", "after": "New"}
        assert result["metadata_diff"]["state"] is None

    def test_state_change_in_metadata(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T", "state": "draft"}, [])
        b = _snap({"title": "T", "state": "ready"}, [])
        result = svc.compute_version_diff(a, b)
        assert result["metadata_diff"]["state"] == {"before": "draft", "after": "ready"}

    def test_added_section(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T"}, [])
        b = _snap({"title": "T"}, [_section("problem", "new content")])
        result = svc.compute_version_diff(a, b)
        assert len(result["sections"]) == 1
        assert result["sections"][0]["change_type"] == SectionChangeType.ADDED

    def test_removed_section(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T"}, [_section("problem", "old content")])
        b = _snap({"title": "T"}, [])
        result = svc.compute_version_diff(a, b)
        assert result["sections"][0]["change_type"] == SectionChangeType.REMOVED

    def test_modified_section_generates_hunks(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T"}, [_section("problem", "line one\nline two\n")])
        b = _snap({"title": "T"}, [_section("problem", "line one\nline modified\n")])
        result = svc.compute_version_diff(a, b)
        sec = result["sections"][0]
        assert sec["change_type"] == SectionChangeType.MODIFIED
        assert len(sec["hunks"]) > 0

    def test_reordered_section(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T"}, [_section("problem", "x", order=0), _section("goal", "y", order=1)])
        b = _snap({"title": "T"}, [_section("problem", "x", order=1), _section("goal", "y", order=0)])
        result = svc.compute_version_diff(a, b)
        types = {s["section_type"]: s["change_type"] for s in result["sections"]}
        # content unchanged but order changed
        assert types["problem"] == SectionChangeType.REORDERED or types["problem"] == SectionChangeType.UNCHANGED

    def test_from_version_greater_raises(self) -> None:
        svc = DiffService()
        with pytest.raises(ValueError, match="from_version"):
            svc.validate_version_order(from_version=3, to_version=1)

    def test_empty_source_all_added(self) -> None:
        svc = DiffService()
        a = _snap({"title": "T"}, [])
        b = _snap({"title": "T"}, [_section("problem", "content"), _section("goal", "content2")])
        result = svc.compute_version_diff(a, b)
        assert all(s["change_type"] == SectionChangeType.ADDED for s in result["sections"])


class TestComputeSectionDiff:
    def test_identical_returns_no_diff_lines(self) -> None:
        svc = DiffService()
        result = svc.compute_section_diff("line one\nline two\n", "line one\nline two\n")
        # Either no hunks or only context lines
        for hunk in result:
            assert all(line["type"] == "context" for line in hunk["lines"])

    def test_added_lines_marked(self) -> None:
        svc = DiffService()
        result = svc.compute_section_diff("a\n", "a\nb\n")
        all_types = [line["type"] for hunk in result for line in hunk["lines"]]
        assert "added" in all_types

    def test_removed_lines_marked(self) -> None:
        svc = DiffService()
        result = svc.compute_section_diff("a\nb\n", "a\n")
        all_types = [line["type"] for hunk in result for line in hunk["lines"]]
        assert "removed" in all_types

    def test_performance_100kb_under_2s(self) -> None:
        svc = DiffService()
        # ~50KB per side
        text_a = ("line of text here\n" * 2800)
        text_b = ("line of text here\n" * 2799) + "modified line\n"
        start = time.perf_counter()
        svc.compute_section_diff(text_a, text_b)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"diff took {elapsed:.2f}s, exceeds 2s limit"
