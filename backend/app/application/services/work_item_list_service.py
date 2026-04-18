"""EP-09 — WorkItemListQueryBuilder.

Builds SQLAlchemy SELECT statements for the advanced work-items list endpoint.
No DB access here — pure statement construction for testability.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, exists, func, or_, select

from app.domain.pagination import PaginationCursor
from app.domain.queries.work_item_list_filters import MineType, SortOption, WorkItemListFilters
from app.infrastructure.persistence.models.orm import (
    ReviewRequestORM,
    TeamMembershipORM,
    WorkItemORM,
)


class WorkItemListQueryBuilder:
    def __init__(
        self,
        *,
        workspace_id: UUID,
        filters: WorkItemListFilters,
        current_user_id: UUID | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._filters = filters
        self._current_user_id = current_user_id
        self._decoded: PaginationCursor | None | _Sentinel = _UNRESOLVED

    @property
    def decoded_cursor(self) -> PaginationCursor | None:
        if isinstance(self._decoded, _Sentinel):
            if self._filters.cursor is None:
                self._decoded = None
            else:
                # Raises ValueError on tamper — caller maps to 422
                self._decoded = PaginationCursor.decode(self._filters.cursor)
        return self._decoded  # type: ignore[return-value]

    def build_stmt(self) -> Select[tuple[WorkItemORM]]:
        f = self._filters
        stmt = select(WorkItemORM).where(
            WorkItemORM.workspace_id == self._workspace_id
        )

        # ------------------------------------------------------------------
        # Filters
        # ------------------------------------------------------------------
        if not f.include_deleted:
            stmt = stmt.where(WorkItemORM.deleted_at.is_(None))

        if f.state:
            stmt = stmt.where(WorkItemORM.state.in_(f.state))

        if f.type:
            stmt = stmt.where(WorkItemORM.type.in_(f.type))

        if f.owner_id is not None:
            stmt = stmt.where(WorkItemORM.owner_id == f.owner_id)

        if f.creator_id is not None:
            stmt = stmt.where(WorkItemORM.creator_id == f.creator_id)

        if f.parent_work_item_id is not None:
            stmt = stmt.where(WorkItemORM.parent_work_item_id == f.parent_work_item_id)

        if f.has_override is not None:
            stmt = stmt.where(WorkItemORM.has_override == f.has_override)

        if f.project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == f.project_id)

        if f.priority:
            stmt = stmt.where(WorkItemORM.priority.in_(f.priority))

        if f.completeness_min is not None:
            stmt = stmt.where(WorkItemORM.completeness_score >= f.completeness_min)

        if f.completeness_max is not None:
            stmt = stmt.where(WorkItemORM.completeness_score <= f.completeness_max)

        if f.updated_after is not None:
            stmt = stmt.where(WorkItemORM.updated_at >= f.updated_after)

        if f.updated_before is not None:
            stmt = stmt.where(WorkItemORM.updated_at <= f.updated_before)

        if f.tag_id:
            # AND semantics: item must contain ALL listed tags
            for tag in f.tag_id:
                stmt = stmt.where(WorkItemORM.tags.contains([tag]))

        if f.q and not f.use_puppet:
            stmt = stmt.where(WorkItemORM.title.ilike(f"%{f.q}%"))

        # ------------------------------------------------------------------
        # Mine filter
        # ------------------------------------------------------------------
        if f.mine and self._current_user_id is not None:
            stmt = self._apply_mine_filter(stmt, f.mine_type, self._current_user_id)

        # ------------------------------------------------------------------
        # Cursor keyset condition
        # ------------------------------------------------------------------
        cursor = self.decoded_cursor  # raises ValueError if tampered
        if cursor is not None:
            stmt = self._apply_cursor(stmt, cursor, f.sort)

        # ------------------------------------------------------------------
        # Sort
        # ------------------------------------------------------------------
        stmt = self._apply_sort(stmt, f.sort)

        # ------------------------------------------------------------------
        # Limit (fetch limit+1 to detect next page)
        # ------------------------------------------------------------------
        stmt = stmt.limit(f.limit + 1)

        return stmt

    def build_count_stmt(self) -> Select[tuple[int]]:
        """Count query with the same WHERE clause (no sort/limit)."""
        f = self._filters
        stmt = select(func.count()).select_from(WorkItemORM).where(
            WorkItemORM.workspace_id == self._workspace_id
        )
        if not f.include_deleted:
            stmt = stmt.where(WorkItemORM.deleted_at.is_(None))
        if f.state:
            stmt = stmt.where(WorkItemORM.state.in_(f.state))
        if f.type:
            stmt = stmt.where(WorkItemORM.type.in_(f.type))
        if f.owner_id is not None:
            stmt = stmt.where(WorkItemORM.owner_id == f.owner_id)
        if f.creator_id is not None:
            stmt = stmt.where(WorkItemORM.creator_id == f.creator_id)
        if f.parent_work_item_id is not None:
            stmt = stmt.where(WorkItemORM.parent_work_item_id == f.parent_work_item_id)
        if f.has_override is not None:
            stmt = stmt.where(WorkItemORM.has_override == f.has_override)
        if f.project_id is not None:
            stmt = stmt.where(WorkItemORM.project_id == f.project_id)
        if f.priority:
            stmt = stmt.where(WorkItemORM.priority.in_(f.priority))
        if f.completeness_min is not None:
            stmt = stmt.where(WorkItemORM.completeness_score >= f.completeness_min)
        if f.completeness_max is not None:
            stmt = stmt.where(WorkItemORM.completeness_score <= f.completeness_max)
        if f.updated_after is not None:
            stmt = stmt.where(WorkItemORM.updated_at >= f.updated_after)
        if f.updated_before is not None:
            stmt = stmt.where(WorkItemORM.updated_at <= f.updated_before)
        if f.tag_id:
            for tag in f.tag_id:
                stmt = stmt.where(WorkItemORM.tags.contains([tag]))
        if f.q and not f.use_puppet:
            stmt = stmt.where(WorkItemORM.title.ilike(f"%{f.q}%"))
        return stmt

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_mine_filter(
        self,
        stmt: Select[Any],
        mine_type: MineType,
        user_id: UUID,
    ) -> Select[Any]:
        """Restrict to items the current user owns, created, or is reviewing.

        Reviewer subquery: items with a pending review_request where the user
        is a direct reviewer OR is a member of a team-type reviewer.
        Uses EXISTS subqueries — no N+1.
        """
        reviewer_subq = (
            select(ReviewRequestORM.work_item_id)
            .where(
                ReviewRequestORM.status == "pending",
                or_(
                    ReviewRequestORM.reviewer_id == user_id,
                    exists(
                        select(TeamMembershipORM.id).where(
                            TeamMembershipORM.team_id == ReviewRequestORM.team_id,
                            TeamMembershipORM.user_id == user_id,
                            TeamMembershipORM.removed_at.is_(None),
                        )
                    ),
                ),
            )
            .correlate_except(ReviewRequestORM)
        )

        if mine_type == MineType.owner:
            return stmt.where(WorkItemORM.owner_id == user_id)

        if mine_type == MineType.creator:
            return stmt.where(WorkItemORM.creator_id == user_id)

        if mine_type == MineType.reviewer:
            return stmt.where(WorkItemORM.id.in_(reviewer_subq))

        # MineType.any — OR of all three
        return stmt.where(
            or_(
                WorkItemORM.owner_id == user_id,
                WorkItemORM.creator_id == user_id,
                WorkItemORM.id.in_(reviewer_subq),
            )
        )

    def _apply_cursor(
        self, stmt: Select[Any], cursor: PaginationCursor, sort: SortOption
    ) -> Select[Any]:
        sv = cursor.sort_value
        last_id = cursor.last_id

        if sort in (SortOption.updated_desc, SortOption.updated_asc):
            # sv is stored as ISO string when sort value is a datetime
            dt_sv = datetime.fromisoformat(sv) if isinstance(sv, str) else sv
            col = WorkItemORM.updated_at
            if sort == SortOption.updated_desc:
                stmt = stmt.where(
                    or_(
                        col < dt_sv,
                        (col == dt_sv) & (WorkItemORM.id < last_id),
                    )
                )
            else:
                stmt = stmt.where(
                    or_(
                        col > dt_sv,
                        (col == dt_sv) & (WorkItemORM.id > last_id),
                    )
                )
        elif sort == SortOption.created_desc:
            dt_sv = datetime.fromisoformat(sv) if isinstance(sv, str) else sv
            col = WorkItemORM.created_at
            stmt = stmt.where(
                or_(
                    col < dt_sv,
                    (col == dt_sv) & (WorkItemORM.id < last_id),
                )
            )
        elif sort == SortOption.title_asc:
            stmt = stmt.where(
                or_(
                    WorkItemORM.title > sv,
                    (WorkItemORM.title == sv) & (WorkItemORM.id > last_id),
                )
            )
        elif sort == SortOption.completeness_desc:
            int_sv = int(sv) if isinstance(sv, str) else sv
            stmt = stmt.where(
                or_(
                    WorkItemORM.completeness_score < int_sv,
                    (WorkItemORM.completeness_score == int_sv) & (WorkItemORM.id < last_id),
                )
            )
        return stmt

    def _apply_sort(self, stmt: Select[Any], sort: SortOption) -> Select[Any]:
        if sort == SortOption.updated_desc:
            return stmt.order_by(WorkItemORM.updated_at.desc(), WorkItemORM.id.desc())
        if sort == SortOption.updated_asc:
            return stmt.order_by(WorkItemORM.updated_at.asc(), WorkItemORM.id.asc())
        if sort == SortOption.created_desc:
            return stmt.order_by(WorkItemORM.created_at.desc(), WorkItemORM.id.desc())
        if sort == SortOption.title_asc:
            return stmt.order_by(WorkItemORM.title.asc(), WorkItemORM.id.asc())
        if sort == SortOption.completeness_desc:
            return stmt.order_by(WorkItemORM.completeness_score.desc(), WorkItemORM.id.desc())
        return stmt.order_by(WorkItemORM.updated_at.desc(), WorkItemORM.id.desc())


class _Sentinel:
    pass


_UNRESOLVED = _Sentinel()
