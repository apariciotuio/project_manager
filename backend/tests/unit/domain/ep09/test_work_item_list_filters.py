"""EP-09 — Unit tests for WorkItemListFilters."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.queries.work_item_list_filters import SortOption, WorkItemListFilters


class TestDefaults:
    def test_all_optional_fields_none_by_default(self) -> None:
        f = WorkItemListFilters()
        assert f.state is None
        assert f.owner_id is None
        assert f.q is None
        assert f.cursor is None

    def test_default_sort(self) -> None:
        f = WorkItemListFilters()
        assert f.sort == SortOption.updated_desc

    def test_default_limit(self) -> None:
        f = WorkItemListFilters()
        assert f.limit == 25


class TestCompletenessValidation:
    def test_min_gt_max_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(completeness_min=80, completeness_max=20)

    def test_equal_min_max_allowed(self) -> None:
        f = WorkItemListFilters(completeness_min=50, completeness_max=50)
        assert f.completeness_min == 50

    def test_min_below_zero_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(completeness_min=-1)

    def test_max_above_100_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(completeness_max=101)


class TestLimitBounds:
    def test_limit_zero_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(limit=0)

    def test_limit_101_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(limit=101)

    def test_limit_100_accepted(self) -> None:
        f = WorkItemListFilters(limit=100)
        assert f.limit == 100


class TestSortOptions:
    def test_all_sort_values_accepted(self) -> None:
        for opt in SortOption:
            f = WorkItemListFilters(sort=opt)
            assert f.sort == opt

    def test_invalid_sort_rejected(self) -> None:
        with pytest.raises(Exception):
            WorkItemListFilters(sort="nonexistent_sort")


class TestTagIds:
    def test_multiple_tag_ids_accepted(self) -> None:
        f = WorkItemListFilters(tag_id=["tag-a", "tag-b"])
        assert f.tag_id == ["tag-a", "tag-b"]

    def test_single_tag_id_accepted(self) -> None:
        f = WorkItemListFilters(tag_id=["tag-a"])
        assert len(f.tag_id) == 1


class TestPuppetToggle:
    def test_use_puppet_false_by_default(self) -> None:
        f = WorkItemListFilters()
        assert f.use_puppet is False

    def test_use_puppet_true_with_q(self) -> None:
        f = WorkItemListFilters(q="auth flow", use_puppet=True)
        assert f.use_puppet is True
        assert f.q == "auth flow"
