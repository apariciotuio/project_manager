"""EP-04 Phase 2 — Section entity invariants."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.section import RequiredSectionEmptyError, Section
from app.domain.models.section_type import GenerationSource, SectionType


def _make(section_type: SectionType = SectionType.SUMMARY, is_required: bool = True) -> Section:
    return Section.create(
        work_item_id=uuid4(),
        section_type=section_type,
        display_order=1,
        is_required=is_required,
        created_by=uuid4(),
    )


def test_create_starts_at_version_one() -> None:
    s = _make()
    assert s.version == 1
    assert s.content == ""
    assert s.generation_source is GenerationSource.LLM


def test_update_content_increments_version() -> None:
    s = _make()
    actor = uuid4()
    s.update_content("new content here meets the minimum", actor)
    assert s.version == 2
    assert s.content.startswith("new content")
    assert s.updated_by == actor
    assert s.generation_source is GenerationSource.MANUAL


def test_update_content_rejects_empty_on_required() -> None:
    s = _make(is_required=True)
    with pytest.raises(RequiredSectionEmptyError):
        s.update_content("   ", uuid4())


def test_update_content_allows_empty_on_optional() -> None:
    s = _make(is_required=False)
    s.update_content("", uuid4())
    assert s.content == ""
    assert s.version == 2


def test_update_content_propagates_source() -> None:
    s = _make()
    s.update_content("body text of sufficient length", uuid4(), source=GenerationSource.REVERT)
    assert s.generation_source is GenerationSource.REVERT
