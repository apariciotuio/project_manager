"""Tests for content_quality gap detection rule."""

from __future__ import annotations

from uuid import uuid4

from app.domain.gap_detection.rules.content_quality import check_content_quality
from app.domain.models.gap_finding import GapFinding, GapSeverity
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType


def _work_item(
    *,
    description: str | None = None,
    title: str = "Valid title",
    type: WorkItemType = WorkItemType.TASK,
) -> WorkItem:
    return WorkItem.create(
        title=title,
        type=type,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
        description=description,
    )


class TestDescriptionLength:
    def test_no_description_returns_empty(self) -> None:
        """No description — required_fields handles this; content_quality skips None."""
        item = _work_item(description=None)
        result = check_content_quality(item)
        assert result == []

    def test_empty_description_returns_empty(self) -> None:
        """Empty string — required_fields handles this."""
        item = _work_item(description="")
        result = check_content_quality(item)
        assert result == []

    def test_description_under_50_chars_returns_warning(self) -> None:
        item = _work_item(description="Too short")  # 9 chars
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_description_exactly_50_chars_no_gap(self) -> None:
        item = _work_item(description="A" * 50)
        result = check_content_quality(item)
        length_gaps = [
            f for f in result if f.dimension == "description" and "short" in f.message.lower()
        ]
        assert length_gaps == []

    def test_description_49_chars_returns_warning(self) -> None:
        item = _work_item(description="A" * 49)
        result = check_content_quality(item)
        assert any(
            f.dimension == "description" and f.severity == GapSeverity.WARNING for f in result
        )

    def test_description_51_chars_no_length_gap(self) -> None:
        item = _work_item(description="A" * 51)
        result = check_content_quality(item)
        length_gaps = [
            f for f in result if f.dimension == "description" and "short" in f.message.lower()
        ]
        assert length_gaps == []


class TestVaguePhrases:
    def test_tbd_alone_returns_warning(self) -> None:
        item = _work_item(description="TBD")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_todo_alone_returns_warning(self) -> None:
        item = _work_item(description="TODO")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_na_alone_returns_warning(self) -> None:
        item = _work_item(description="N/A")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_tbd_lowercase_returns_warning(self) -> None:
        item = _work_item(description="tbd")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_todo_lowercase_returns_warning(self) -> None:
        item = _work_item(description="todo")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )

    def test_tbd_in_longer_text_no_vague_gap(self) -> None:
        """TBD embedded in longer meaningful text should NOT trigger vague pattern."""
        base = "This is a complete description that mentions TBD but has real content. "
        item = _work_item(description=base * 2)
        result = check_content_quality(item)
        vague_gaps = [
            f for f in result if "vague" in f.message.lower() or "placeholder" in f.message.lower()
        ]
        assert vague_gaps == []

    def test_todo_with_colon_and_content_no_vague_gap(self) -> None:
        """TODO: something is a real annotation, not a vague-only description."""
        base = "TODO: implement the retry logic for the payment gateway integration. "
        item = _work_item(description=base * 2)
        result = check_content_quality(item)
        vague_gaps = [
            f for f in result if "vague" in f.message.lower() or "placeholder" in f.message.lower()
        ]
        assert vague_gaps == []

    def test_whitespace_only_tbd_triggers_warning(self) -> None:
        item = _work_item(description="  TBD  ")
        result = check_content_quality(item)
        assert any(
            f.severity == GapSeverity.WARNING and f.dimension == "description" for f in result
        )


class TestContentQualityReturnType:
    def test_returns_list_of_gap_findings(self) -> None:
        item = _work_item(description="short")
        result = check_content_quality(item)
        assert isinstance(result, list)
        assert all(isinstance(f, GapFinding) for f in result)

    def test_source_is_rule(self) -> None:
        item = _work_item(description="short")
        result = check_content_quality(item)
        assert all(f.source == "rule" for f in result)

    def test_good_description_returns_empty(self) -> None:
        desc = "A well-written description that has more than fifty characters total."
        item = _work_item(description=desc)
        result = check_content_quality(item)
        assert result == []
