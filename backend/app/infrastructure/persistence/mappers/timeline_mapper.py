"""Mapper for TimelineEvent — EP-07."""
from __future__ import annotations

from app.domain.models.timeline_event import TimelineActorType, TimelineEvent
from app.infrastructure.persistence.models.orm import TimelineEventORM


def timeline_event_to_domain(row: TimelineEventORM) -> TimelineEvent:
    return TimelineEvent(
        id=row.id,
        work_item_id=row.work_item_id,
        workspace_id=row.workspace_id,
        event_type=row.event_type,
        actor_type=TimelineActorType(row.actor_type),
        actor_id=row.actor_id,
        actor_display_name=row.actor_display_name,
        summary=row.summary,
        payload=dict(row.payload),
        occurred_at=row.occurred_at,
        source_id=row.source_id,
        source_table=row.source_table,
    )


def timeline_event_to_orm(entity: TimelineEvent) -> TimelineEventORM:
    row = TimelineEventORM()
    row.id = entity.id
    row.work_item_id = entity.work_item_id
    row.workspace_id = entity.workspace_id
    row.event_type = entity.event_type
    row.actor_type = entity.actor_type.value
    row.actor_id = entity.actor_id
    row.actor_display_name = entity.actor_display_name
    row.summary = entity.summary
    row.payload = entity.payload
    row.occurred_at = entity.occurred_at
    row.source_id = entity.source_id
    row.source_table = entity.source_table
    return row
