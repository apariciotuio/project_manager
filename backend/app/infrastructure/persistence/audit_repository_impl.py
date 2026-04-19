"""SQLAlchemy implementation of IAuditRepository."""

from __future__ import annotations

from datetime import timezone, UTC
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.audit_event import AuditEvent
from app.domain.repositories.audit_repository import IAuditRepository
from app.infrastructure.pagination import PaginationCursor, PaginationResult
from app.infrastructure.persistence.models.orm import AuditEventORM


class AuditRepositoryImpl(IAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> AuditEvent:
        row = AuditEventORM(
            id=event.id,
            category=event.category,
            action=event.action,
            actor_id=event.actor_id,
            actor_display=event.actor_display,
            workspace_id=event.workspace_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            before_value=event.before_value,
            after_value=event.after_value,
            context=event.context,
            created_at=event.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return event

    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        category: str | None = None,
        action: str | None = None,
    ) -> PaginationResult:
        """Keyset-paginated list ordered by (created_at DESC, id DESC)."""
        conditions: list[sa.ColumnElement[bool]] = [
            AuditEventORM.workspace_id == workspace_id,
        ]
        if category is not None:
            conditions.append(AuditEventORM.category == category)
        if action is not None:
            conditions.append(AuditEventORM.action == action)

        stmt = select(AuditEventORM).where(*conditions)

        if cursor is not None:
            stmt = stmt.where(
                sa.or_(
                    AuditEventORM.created_at < cursor.created_at,
                    sa.and_(
                        AuditEventORM.created_at == cursor.created_at,
                        sa.cast(AuditEventORM.id, sa.Text) < str(cursor.id),
                    ),
                )
            )

        stmt = stmt.order_by(
            AuditEventORM.created_at.desc(),
            sa.cast(AuditEventORM.id, sa.Text).desc(),
        ).limit(page_size + 1)

        rows = (await self._session.execute(stmt)).scalars().all()
        has_next = len(rows) > page_size
        if has_next:
            rows = rows[:page_size]

        next_cursor: str | None = None
        if has_next and rows:
            last = rows[-1]
            ts = last.created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            next_cursor = PaginationCursor(
                id=UUID(str(last.id)),
                created_at=ts,
            ).encode()

        return PaginationResult(rows=list(rows), has_next=has_next, next_cursor=next_cursor)
