"""EP-08 — Notification mapper."""

from __future__ import annotations

from app.domain.models.team import Notification, NotificationState
from app.infrastructure.persistence.models.orm import NotificationORM


def notification_to_domain(row: NotificationORM) -> Notification:
    return Notification(
        id=row.id,
        workspace_id=row.workspace_id,
        recipient_id=row.recipient_id,
        type=row.type,
        state=NotificationState(row.state),
        actor_id=row.actor_id,
        subject_type=row.subject_type,
        subject_id=row.subject_id,
        deeplink=row.deeplink,
        quick_action=dict(row.quick_action) if row.quick_action else None,
        extra=dict(row.extra) if row.extra else {},
        idempotency_key=row.idempotency_key,
        created_at=row.created_at,
        read_at=row.read_at,
        actioned_at=row.actioned_at,
    )


def notification_to_orm(entity: Notification) -> NotificationORM:
    row = NotificationORM()
    row.id = entity.id
    row.workspace_id = entity.workspace_id
    row.recipient_id = entity.recipient_id
    row.type = entity.type
    row.state = entity.state.value
    row.actor_id = entity.actor_id
    row.subject_type = entity.subject_type
    row.subject_id = entity.subject_id
    row.deeplink = entity.deeplink
    row.quick_action = entity.quick_action
    row.extra = entity.extra
    row.idempotency_key = entity.idempotency_key
    row.created_at = entity.created_at
    row.read_at = entity.read_at
    row.actioned_at = entity.actioned_at
    return row
