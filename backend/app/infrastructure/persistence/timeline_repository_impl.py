"""EP-07 — SQLAlchemy implementation for TimelineEvent repo."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.timeline_event import TimelineEvent
from app.domain.repositories.timeline_repository import ITimelineEventRepository
from app.infrastructure.persistence.mappers.timeline_mapper import (
    timeline_event_to_domain,
    timeline_event_to_orm,
)
from app.infrastructure.persistence.models.orm import TimelineEventORM


class TimelineEventRepositoryImpl(ITimelineEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(self, event: TimelineEvent) -> TimelineEvent:
        self._session.add(timeline_event_to_orm(event))
        await self._session.flush()
        return event

    async def list_for_work_item(
        self,
        work_item_id: UUID,
        *,
        before_occurred_at: datetime | None = None,
        before_id: UUID | None = None,
        limit: int = 50,
        event_types: list[str] | None = None,
        actor_types: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[TimelineEvent]:
        stmt = select(TimelineEventORM).where(
            TimelineEventORM.work_item_id == work_item_id
        )

        if before_occurred_at is not None and before_id is not None:
            # Keyset pagination: (occurred_at, id) DESC
            stmt = stmt.where(
                or_(
                    TimelineEventORM.occurred_at < before_occurred_at,
                    and_(
                        TimelineEventORM.occurred_at == before_occurred_at,
                        TimelineEventORM.id < before_id,
                    ),
                )
            )

        if event_types:
            stmt = stmt.where(TimelineEventORM.event_type.in_(event_types))

        if actor_types:
            stmt = stmt.where(TimelineEventORM.actor_type.in_(actor_types))

        if from_date is not None:
            stmt = stmt.where(TimelineEventORM.occurred_at >= from_date)

        if to_date is not None:
            stmt = stmt.where(TimelineEventORM.occurred_at <= to_date)

        stmt = (
            stmt
            .order_by(
                TimelineEventORM.occurred_at.desc(),
                TimelineEventORM.id.desc(),
            )
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [timeline_event_to_domain(r) for r in rows]
