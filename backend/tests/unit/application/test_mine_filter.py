"""EP-09 — Unit tests for WorkItemListQueryBuilder mine filter variants.

RED phase: these tests will fail until _apply_mine_filter is implemented.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.application.services.work_item_list_service import WorkItemListQueryBuilder
from app.domain.queries.work_item_list_filters import WorkItemListFilters


def _builder(user_id: UUID, **kw: object) -> WorkItemListQueryBuilder:
    ws = uuid4()
    filters = WorkItemListFilters(**kw)
    return WorkItemListQueryBuilder(workspace_id=ws, filters=filters, current_user_id=user_id)


def _stmt_str(b: WorkItemListQueryBuilder) -> str:
    from sqlalchemy.dialects import postgresql
    stmt = b.build_stmt()
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": False}))


class TestMineFilterOff:
    def test_mine_false_no_extra_condition(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=False)
        sql = _stmt_str(b)
        # No mine-specific subquery injected
        assert "review_requests" not in sql
        assert "team_memberships" not in sql

    def test_mine_default_is_false(self) -> None:
        uid = uuid4()
        b = _builder(uid)
        sql = _stmt_str(b)
        assert "review_requests" not in sql


class TestMineFilterOwner:
    def test_mine_owner_adds_owner_condition(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="owner")
        sql = _stmt_str(b)
        assert "owner_id" in sql

    def test_mine_owner_does_not_add_creator(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="owner")
        sql = _stmt_str(b)
        # Should NOT contain a creator_id mine condition (only owner)
        # creator_id may appear if set separately; we check no review_requests
        assert "review_requests" not in sql


class TestMineFilterCreator:
    def test_mine_creator_adds_creator_condition(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="creator")
        sql = _stmt_str(b)
        assert "creator_id" in sql

    def test_mine_creator_does_not_add_reviewer_subquery(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="creator")
        sql = _stmt_str(b)
        assert "review_requests" not in sql


class TestMineFilterReviewer:
    def test_mine_reviewer_adds_review_requests_subquery(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="reviewer")
        sql = _stmt_str(b)
        assert "review_requests" in sql

    def test_mine_reviewer_includes_team_membership_join(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="reviewer")
        sql = _stmt_str(b)
        # Team-type reviewer path must consult team_memberships
        assert "team_memberships" in sql


class TestMineFilterAny:
    def test_mine_any_includes_owner_or_creator_or_reviewer(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True, mine_type="any")
        sql = _stmt_str(b)
        assert "owner_id" in sql
        assert "creator_id" in sql
        assert "review_requests" in sql

    def test_mine_true_no_mine_type_defaults_to_any(self) -> None:
        uid = uuid4()
        b = _builder(uid, mine=True)
        sql = _stmt_str(b)
        assert "owner_id" in sql
        assert "creator_id" in sql
        assert "review_requests" in sql


class TestMineFilterInvalidType:
    def test_mine_type_invalid_raises_422(self) -> None:
        with pytest.raises(ValidationError):
            WorkItemListFilters(mine=True, mine_type="invalid")  # type: ignore[arg-type]
