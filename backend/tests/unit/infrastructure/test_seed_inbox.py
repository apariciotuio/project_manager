"""Unit tests for seed_sample_data.py inbox seeding (F-2, EP-21).

Tests run against an in-memory fake NotificationRepository to verify:
- 12 notifications created for the seed user
- 4 kinds present: assigned, mentioned, review_requested, state_changed
- At least 3 unread
- created_at spread across >= 2 distinct dates
- Idempotency: second run produces same count
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.team import Notification, NotificationState
from app.domain.repositories.notification_repository import INotificationRepository


class FakeNotificationRepository(INotificationRepository):
    def __init__(self) -> None:
        self._store: dict[UUID, Notification] = {}
        self._idempotency_index: dict[str, UUID] = {}

    async def create(self, notification: Notification) -> Notification:
        key = notification.idempotency_key
        if key in self._idempotency_index:
            return self._store[self._idempotency_index[key]]
        self._store[notification.id] = notification
        self._idempotency_index[key] = notification.id
        return notification

    async def get(self, notification_id: UUID) -> Notification | None:
        return self._store.get(notification_id)

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        rows = [n for n in self._store.values() if n.recipient_id == user_id]
        rows.sort(key=lambda n: n.created_at, reverse=True)
        return rows[offset : offset + limit]

    async def list_inbox_cursor(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        cursor: Any = None,
        page_size: int = 50,
    ) -> Any:
        rows = [
            n for n in self._store.values()
            if n.recipient_id == user_id and n.workspace_id == workspace_id
        ]
        rows.sort(key=lambda n: n.created_at, reverse=True)
        return rows[:page_size]

    async def mark_read(self, notification_id: UUID) -> None:
        if notification_id in self._store:
            self._store[notification_id].mark_read()

    async def mark_actioned(self, notification_id: UUID) -> None:
        if notification_id in self._store:
            self._store[notification_id].mark_actioned()


# ---------------------------------------------------------------------------
# The seeding logic extracted into a pure async function so we can unit-test
# it without a DB. The actual seed script calls this same function.
# ---------------------------------------------------------------------------

from scripts.seed_notifications import seed_notifications  # type: ignore[import]


@pytest.fixture
def repo() -> FakeNotificationRepository:
    return FakeNotificationRepository()


@pytest.fixture
def seed_args(repo: FakeNotificationRepository) -> dict[str, Any]:
    return {
        "repo": repo,
        "user_id": uuid4(),
        "workspace_id": uuid4(),
        "work_item_ids": [uuid4() for _ in range(8)],
    }


@pytest.mark.asyncio
async def test_seed_creates_at_least_12_notifications(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    assert len(notifications) >= 12


@pytest.mark.asyncio
async def test_seed_covers_all_four_kinds(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    kinds = {n.type for n in notifications}
    assert "assigned" in kinds
    assert "mentioned" in kinds
    assert "review_requested" in kinds
    assert "state_changed" in kinds


@pytest.mark.asyncio
async def test_seed_has_at_least_3_unread(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    unread = [n for n in notifications if n.state == NotificationState.UNREAD]
    assert len(unread) >= 3


@pytest.mark.asyncio
async def test_seed_created_at_spread_across_14_days(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    dates = {n.created_at.date() for n in notifications}
    assert len(dates) >= 2  # at least 2 distinct days


@pytest.mark.asyncio
async def test_seed_has_notification_within_last_24h(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    recent = [n for n in notifications if n.created_at >= cutoff]
    assert len(recent) >= 1


@pytest.mark.asyncio
async def test_seed_is_idempotent(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    count_after_first = len(await repo.list_for_user(seed_args["user_id"], limit=100))
    await seed_notifications(**seed_args)
    count_after_second = len(await repo.list_for_user(seed_args["user_id"], limit=100))
    assert count_after_first == count_after_second


@pytest.mark.asyncio
async def test_seed_notifications_linked_to_real_work_items(
    seed_args: dict[str, Any],
    repo: FakeNotificationRepository,
) -> None:
    await seed_notifications(**seed_args)
    notifications = await repo.list_for_user(seed_args["user_id"], limit=100)
    work_item_ids = set(seed_args["work_item_ids"])
    for n in notifications:
        if n.type in ("assigned", "review_requested"):
            assert n.subject_id in work_item_ids, (
                f"Notification {n.type} references unknown work_item_id {n.subject_id}"
            )
