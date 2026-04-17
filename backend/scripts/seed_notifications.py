"""Seed inbox notifications for dev/QA environments.

Callable from seed_sample_data.py and directly unit-tested.
Idempotency: keyed on (user_id, work_item_id, kind) via the repository's
create path — the FakeNotificationRepository and the real Postgres impl
both skip on duplicate idempotency_key.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.models.team import Notification
from app.domain.repositories.notification_repository import INotificationRepository

# 12 seed entries: (kind, work_item_index, days_ago, read)
_SEED_ENTRIES: list[tuple[str, int, int, bool]] = [
    # assigned (4)
    ("assigned", 0, 14, True),
    ("assigned", 1, 10, True),
    ("assigned", 2, 5, False),
    ("assigned", 3, 0, False),
    # mentioned (3)
    ("mentioned", 0, 12, True),
    ("mentioned", 2, 6, False),
    ("mentioned", 4, 1, False),
    # review_requested (3)
    ("review_requested", 1, 9, True),
    ("review_requested", 3, 4, False),
    ("review_requested", 5, 0, False),
    # state_changed (2)
    ("state_changed", 6, 8, True),
    ("state_changed", 7, 2, False),
]


async def seed_notifications(
    *,
    repo: INotificationRepository,
    user_id: UUID,
    workspace_id: UUID,
    work_item_ids: list[UUID],
) -> int:
    """Create seed notifications.  Returns count of newly created rows."""
    now = datetime.now(UTC)
    created = 0

    for kind, wi_idx, days_ago, is_read in _SEED_ENTRIES:
        wi_id = work_item_ids[wi_idx % len(work_item_ids)]
        idempotency_key = f"seed:{user_id}:{wi_id}:{kind}"
        created_at = now - timedelta(days=days_ago, hours=days_ago % 5)

        notification = Notification.create(
            workspace_id=workspace_id,
            recipient_id=user_id,
            type=kind,
            actor_id=user_id,
            subject_type="work_item",
            subject_id=wi_id,
            deeplink=f"/work-items/{wi_id}",
            idempotency_key=idempotency_key,
        )
        # Override created_at to spread across 14 days
        notification.created_at = created_at

        if is_read:
            notification.mark_read()

        existing = await repo.create(notification)
        # If idempotency_key was fresh we get back our notification;
        # detect new vs skip by comparing ids
        if existing.id == notification.id:
            created += 1

    return created
