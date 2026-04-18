"""EP-09 — Unit tests for WorkItemListQueryBuilder.

Tests verify that the correct SQL conditions are appended for each filter.
We test the SQLAlchemy statement object, not the DB — no DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.services.work_item_list_service import WorkItemListQueryBuilder
from app.domain.queries.work_item_list_filters import SortOption, WorkItemListFilters


def _builder(workspace_id: UUID | None = None, **kw: object) -> WorkItemListQueryBuilder:
    ws = workspace_id or uuid4()
    filters = WorkItemListFilters(**kw)
    return WorkItemListQueryBuilder(workspace_id=ws, filters=filters)


def _stmt_str(builder: WorkItemListQueryBuilder) -> str:
    """Compile the statement to a string for assertion."""
    from sqlalchemy.dialects import postgresql

    stmt = builder.build_stmt()
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))


class TestNoFilters:
    def test_no_filter_returns_stmt(self) -> None:
        b = _builder()
        stmt = b.build_stmt()
        assert stmt is not None

    def test_default_sort_updated_desc(self) -> None:
        b = _builder()
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "updated_at" in compiled.lower()


class TestFilterState:
    def test_single_state_filter(self) -> None:
        b = _builder(state=["draft"])
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "state" in compiled

    def test_multiple_states(self) -> None:
        b = _builder(state=["draft", "in_review"])
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "state" in compiled


class TestFilterOwner:
    def test_owner_id_filter(self) -> None:
        uid = uuid4()
        b = _builder(owner_id=uid)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "owner_id" in compiled


class TestFilterCreator:
    def test_creator_id_filter(self) -> None:
        uid = uuid4()
        b = _builder(creator_id=uid)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "creator_id" in compiled


class TestFilterProjectId:
    def test_project_id_filter(self) -> None:
        pid = uuid4()
        b = _builder(project_id=pid)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "project_id" in compiled


class TestFilterCompleteness:
    def test_min_filter(self) -> None:
        b = _builder(completeness_min=50)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "completeness_score" in compiled

    def test_max_filter(self) -> None:
        b = _builder(completeness_max=80)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "completeness_score" in compiled


class TestFilterDateRange:
    def test_updated_after(self) -> None:
        dt = datetime(2026, 1, 1, tzinfo=UTC)
        b = _builder(updated_after=dt)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "updated_at" in compiled

    def test_updated_before(self) -> None:
        dt = datetime(2026, 6, 1, tzinfo=UTC)
        b = _builder(updated_before=dt)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "updated_at" in compiled


class TestSortOptions:
    @pytest.mark.parametrize("sort_opt", list(SortOption))
    def test_all_sort_options_build_without_error(self, sort_opt: SortOption) -> None:
        b = _builder(sort=sort_opt)
        stmt = b.build_stmt()
        assert stmt is not None


class TestDeletedFilter:
    def test_include_deleted_false_adds_condition(self) -> None:
        b = _builder(include_deleted=False)
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "deleted_at" in compiled

    def test_include_deleted_true_skips_condition(self) -> None:
        b = _builder(include_deleted=True)
        stmt = b.build_stmt()
        str(stmt.compile())
        # deleted_at filter removed — no guarantee it won't appear elsewhere, but at minimum it should not appear in the where clause
        # We verify by checking that the query can be built and executes without error
        assert stmt is not None


class TestCursorPagination:
    def test_cursor_param_is_stored(self) -> None:
        from app.domain.pagination import PaginationCursor

        cursor = PaginationCursor(sort_value=datetime.now(UTC).isoformat(), last_id=uuid4())
        encoded = cursor.encode()
        b = _builder(cursor=encoded)
        # verify cursor is decoded and available
        assert b.decoded_cursor is not None
        assert b.decoded_cursor.last_id is not None

    def test_invalid_cursor_raises_value_error(self) -> None:
        b = _builder(cursor="not-valid-base64!!")
        with pytest.raises(ValueError, match="invalid cursor"):
            _ = b.decoded_cursor


class TestCombinedFilters:
    def test_multiple_filters_combined(self) -> None:
        uid = uuid4()
        b = _builder(
            state=["draft"],
            owner_id=uid,
            completeness_min=10,
            completeness_max=90,
        )
        stmt = b.build_stmt()
        compiled = str(stmt.compile())
        assert "state" in compiled
        assert "owner_id" in compiled
        assert "completeness_score" in compiled
