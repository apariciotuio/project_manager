"""SQLAlchemy implementation of IWorkItemRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import InvalidWorkItemError, UserNotFoundError
from app.domain.models.work_item import WorkItem
from app.domain.pagination import PaginationCursor as DomainPaginationCursor
from app.domain.queries.page import Page
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.queries.work_item_list_filters import SortOption, WorkItemListFilters
from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.state_transition import StateTransition
from app.infrastructure.pagination import PaginationCursor, PaginationResult
from app.infrastructure.persistence.mappers import (
    ownership_record_mapper,
    state_transition_mapper,
    work_item_mapper,
)
from app.infrastructure.persistence.models.orm import (
    OwnershipHistoryORM,
    StateTransitionORM,
    WorkItemORM,
)

# CHECK constraint name fragments used for error classification
_CHECK_TITLE = "work_items_title_length"
_CHECK_COMPLETENESS = "work_items_completeness_range"
_CHECK_TYPE = "work_items_type_valid"
_CHECK_STATE = "work_items_state_valid"
_CHECK_PRIORITY = "work_items_priority_valid"
_CHECK_ATTACHMENT = "work_items_attachment_count_nonneg"

_USER_FK_COLUMNS = {"owner_id", "creator_id"}


class WorkItemRepositoryImpl(IWorkItemRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, item_id: UUID, workspace_id: UUID) -> WorkItem | None:
        stmt = select(WorkItemORM).where(
            WorkItemORM.id == item_id,
            WorkItemORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return work_item_mapper.to_domain(row) if row else None

    async def exists_in_workspace(self, item_id: UUID, workspace_id: UUID) -> bool:
        stmt = (
            select(WorkItemORM.id)
            .where(
                WorkItemORM.id == item_id,
                WorkItemORM.workspace_id == workspace_id,
            )
            .limit(1)
        )
        return (await self._session.execute(stmt)).first() is not None

    async def list(
        self,
        workspace_id: UUID,
        project_id: UUID,
        filters: WorkItemFilters,
    ) -> Page[WorkItem]:
        base = select(
            WorkItemORM,
            func.count().over().label("total_count"),
        ).where(
            WorkItemORM.workspace_id == workspace_id,
            WorkItemORM.project_id == project_id,
        )

        if not filters.include_deleted:
            base = base.where(WorkItemORM.deleted_at.is_(None))
        if filters.state is not None:
            base = base.where(WorkItemORM.state == filters.state.value)
        if filters.type is not None:
            base = base.where(WorkItemORM.type == filters.type.value)
        if filters.owner_id is not None:
            base = base.where(WorkItemORM.owner_id == filters.owner_id)
        if filters.has_override is not None:
            base = base.where(WorkItemORM.has_override == filters.has_override)

        offset = (filters.page - 1) * filters.page_size
        base = base.order_by(WorkItemORM.updated_at.desc()).offset(offset).limit(filters.page_size)

        rows = (await self._session.execute(base)).all()
        if not rows:
            return Page(items=[], total=0, page=filters.page, page_size=filters.page_size)

        total = rows[0].total_count
        items = [work_item_mapper.to_domain(row.WorkItemORM) for row in rows]
        return Page(items=items, total=total, page=filters.page, page_size=filters.page_size)

    async def save(self, item: WorkItem, workspace_id: UUID) -> WorkItem:
        values = _build_values(item, workspace_id)
        stmt = (
            pg_insert(WorkItemORM)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[WorkItemORM.id],
                set_={k: v for k, v in values.items() if k != "id"},
            )
            .returning(WorkItemORM)
        )
        try:
            result = await self._session.execute(stmt)
            row = result.scalar_one()
            await self._session.flush()
        except IntegrityError as exc:
            raise _classify_integrity_error(exc) from exc
        return work_item_mapper.to_domain(row)

    async def delete(self, item_id: UUID, workspace_id: UUID) -> None:
        stmt = (
            update(WorkItemORM)
            .where(
                WorkItemORM.id == item_id,
                WorkItemORM.workspace_id == workspace_id,
            )
            .values(deleted_at=func.now())
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def record_transition(
        self, transition: StateTransition, workspace_id: UUID
    ) -> None:
        row = state_transition_mapper.to_orm(transition, workspace_id=workspace_id)
        self._session.add(row)
        await self._session.flush()

    async def record_ownership_change(
        self,
        record: OwnershipRecord,
        workspace_id: UUID,
        previous_owner_id: UUID | None = None,
    ) -> None:
        row = ownership_record_mapper.to_orm(
            record,
            workspace_id=workspace_id,
            previous_owner_id=previous_owner_id,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_transitions(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[StateTransition]:
        stmt = (
            select(StateTransitionORM)
            .where(
                StateTransitionORM.work_item_id == item_id,
                StateTransitionORM.workspace_id == workspace_id,
            )
            .order_by(StateTransitionORM.triggered_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [state_transition_mapper.to_domain(r) for r in rows]

    async def get_ownership_history(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[OwnershipRecord]:
        stmt = (
            select(OwnershipHistoryORM)
            .where(
                OwnershipHistoryORM.work_item_id == item_id,
                OwnershipHistoryORM.workspace_id == workspace_id,
            )
            .order_by(OwnershipHistoryORM.changed_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [ownership_record_mapper.to_domain(r) for r in rows]

    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        filters: WorkItemListFilters | None = None,
        current_user_id: UUID | None = None,
    ) -> PaginationResult:
        from app.application.services.work_item_list_service import WorkItemListQueryBuilder

        if filters is None:
            filters = WorkItemListFilters()

        # Encode the infra cursor (id, created_at) into a domain cursor
        # (sort_value, last_id) so WorkItemListQueryBuilder can apply keyset.
        # Default sort is updated_desc — but list_cursor is invoked from the
        # controller which now passes the sort from filters, so we use whatever
        # sort the filters specify. For the (id, created_at) infra cursor coming
        # from old callers: they are no longer produced — the controller now
        # produces domain cursors.  cursor param here is always None (no infra
        # cursor) or a DomainPaginationCursor re-cast via the controller.
        # We piggyback the domain cursor into filters.cursor (already a str).
        # The builder decodes filters.cursor internally via PaginationCursor.decode.

        builder = WorkItemListQueryBuilder(
            workspace_id=workspace_id,
            filters=filters,
            current_user_id=current_user_id,
        )
        stmt = builder.build_stmt()

        rows = (await self._session.execute(stmt)).scalars().all()
        has_next = len(rows) > page_size
        if has_next:
            rows = rows[:page_size]

        next_cursor: str | None = None
        if has_next and rows:
            last = rows[-1]
            sort = filters.sort
            if sort == SortOption.updated_desc or sort == SortOption.updated_asc:
                ts = last.updated_at
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                sv: object = ts.isoformat() if ts else ""
            elif sort == SortOption.created_desc:
                ts = last.created_at
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                sv = ts.isoformat() if ts else ""
            elif sort == SortOption.title_asc:
                sv = last.title
            elif sort == SortOption.completeness_desc:
                sv = last.completeness_score or 0
            else:
                ts = last.created_at
                if ts is not None and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                sv = ts.isoformat() if ts else ""

            from uuid import UUID as _UUID
            next_cursor = DomainPaginationCursor(
                sort_value=sv,
                last_id=_UUID(str(last.id)),
            ).encode()

        return PaginationResult(
            rows=[work_item_mapper.to_domain(r) for r in rows],
            has_next=has_next,
            next_cursor=next_cursor,
        )


def _build_values(item: WorkItem, workspace_id: UUID) -> dict[str, object]:
    return {
        "id": item.id,
        "workspace_id": workspace_id,
        "project_id": item.project_id,
        "title": item.title,
        "type": item.type.value,
        "state": item.state.value,
        "owner_id": item.owner_id,
        "creator_id": item.creator_id,
        "description": item.description,
        "original_input": item.original_input,
        "priority": item.priority.value if item.priority is not None else None,
        "due_date": item.due_date,
        "tags": item.tags,
        "completeness_score": item.completeness_score,
        "parent_work_item_id": item.parent_work_item_id,
        "materialized_path": item.materialized_path,
        "attachment_count": item.attachment_count,
        "has_override": item.has_override,
        "override_justification": item.override_justification,
        "owner_suspended_flag": item.owner_suspended_flag,
        "draft_data": item.draft_data,
        "template_id": item.template_id,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "deleted_at": item.deleted_at,
        "exported_at": item.exported_at,
        "export_reference": item.export_reference,
        "external_jira_key": item.external_jira_key,
    }


def _classify_integrity_error(exc: IntegrityError) -> Exception:
    msg = str(exc.orig).lower()

    # FK violation on user columns
    if "owner_id" in msg or "creator_id" in msg:
        if "foreign key" in msg or "fk" in msg or "violates" in msg:
            # Extract UUID from message if possible; fall back to zero UUID
            from uuid import UUID as _UUID
            return UserNotFoundError(_UUID(int=0))

    # CHECK constraint violations
    if _CHECK_TITLE in msg:
        return InvalidWorkItemError("title", "length must be between 3 and 255 characters")
    if _CHECK_COMPLETENESS in msg:
        return InvalidWorkItemError("completeness_score", "must be between 0 and 100")
    if _CHECK_TYPE in msg:
        return InvalidWorkItemError("type", "not a valid WorkItemType")
    if _CHECK_STATE in msg:
        return InvalidWorkItemError("state", "not a valid WorkItemState")
    if _CHECK_PRIORITY in msg:
        return InvalidWorkItemError("priority", "must be low, medium, high, or critical")
    if _CHECK_ATTACHMENT in msg:
        return InvalidWorkItemError("attachment_count", "must be >= 0")

    # TODO(EP-10): when project FK is added, classify project_id FK violations here

    return exc
