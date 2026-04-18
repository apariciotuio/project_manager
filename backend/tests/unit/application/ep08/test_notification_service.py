"""EP-08 — Unit tests for NotificationService extensions.

RED phase: tests for mark_all_read, unread_count, bulk_insert_idempotent,
and IDOR check on list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.models.team import Notification, NotificationState
from app.domain.queries.page import Page

# ---------------------------------------------------------------------------
# Fake repository
# ---------------------------------------------------------------------------


class FakeNotificationRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Notification] = {}
        self._idempotency: dict[str, UUID] = {}

    async def create(self, notification: Notification) -> Notification:
        existing = self._idempotency.get(notification.idempotency_key)
        if existing is not None:
            return self._store[existing]
        self._store[notification.id] = notification
        self._idempotency[notification.idempotency_key] = notification.id
        return notification

    async def bulk_insert_idempotent(self, notifications: list[Notification]) -> list[Notification]:
        """Insert all, skipping duplicates. Returns persisted list."""
        result = []
        for n in notifications:
            persisted = await self.create(n)
            result.append(persisted)
        return result

    async def get_by_idempotency_key(self, key: str) -> Notification | None:
        nid = self._idempotency.get(key)
        return self._store.get(nid) if nid else None

    async def get(self, notification_id: UUID) -> Notification | None:
        return self._store.get(notification_id)

    async def list_unread_for_user(
        self,
        user_id: UUID,
        workspace_id: UUID,
        page: int,
        page_size: int,
    ) -> Page[Notification]:
        items = [
            n
            for n in self._store.values()
            if n.recipient_id == user_id and n.workspace_id == workspace_id
        ]
        items.sort(key=lambda n: n.created_at, reverse=True)
        total = len(items)
        start = (page - 1) * page_size
        return Page(
            items=items[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def save(self, notification: Notification) -> Notification:
        self._store[notification.id] = notification
        return notification

    async def unread_count(self, user_id: UUID, workspace_id: UUID) -> int:
        return sum(
            1
            for n in self._store.values()
            if n.recipient_id == user_id
            and n.workspace_id == workspace_id
            and n.state == NotificationState.UNREAD
        )

    async def mark_all_read(self, user_id: UUID, workspace_id: UUID) -> int:
        count = 0
        now = datetime.now(UTC)
        for n in self._store.values():
            if (
                n.recipient_id == user_id
                and n.workspace_id == workspace_id
                and n.state == NotificationState.UNREAD
            ):
                n.state = NotificationState.READ
                n.read_at = now
                count += 1
        return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_notification(
    recipient_id: UUID,
    workspace_id: UUID,
    *,
    state: NotificationState = NotificationState.UNREAD,
    idempotency_key: str | None = None,
) -> Notification:
    n = Notification.create(
        workspace_id=workspace_id,
        recipient_id=recipient_id,
        type="review.assigned",
        subject_type="review",
        subject_id=uuid4(),
        deeplink="/items/x",
        idempotency_key=idempotency_key or str(uuid4()),
    )
    if state == NotificationState.READ:
        n.mark_read()
    elif state == NotificationState.ACTIONED:
        n.mark_actioned()
    return n


# ---------------------------------------------------------------------------
# NotificationService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_idempotent_on_duplicate_key() -> None:
    from app.application.services.team_service import NotificationService

    repo = FakeNotificationRepository()
    svc = NotificationService(notification_repo=repo)
    ws_id = uuid4()
    user_id = uuid4()

    first = await svc.enqueue(
        workspace_id=ws_id,
        recipient_id=user_id,
        type="review.assigned",
        subject_type="review",
        subject_id=uuid4(),
        deeplink="/items/x",
        idempotency_key="key-1",
    )
    second = await svc.enqueue(
        workspace_id=ws_id,
        recipient_id=user_id,
        type="review.assigned",
        subject_type="review",
        subject_id=uuid4(),
        deeplink="/items/x",
        idempotency_key="key-1",  # same key
    )
    # Should return the same notification
    assert first.id == second.id
    assert len(repo._store) == 1


@pytest.mark.asyncio
async def test_mark_read_idempotent_on_already_read() -> None:
    from app.application.services.team_service import NotificationService

    repo = FakeNotificationRepository()
    svc = NotificationService(notification_repo=repo)
    n = _make_notification(uuid4(), uuid4())
    await repo.create(n)
    first = await svc.mark_read(n.id)
    read_at = first.read_at
    second = await svc.mark_read(n.id)
    assert second.read_at == read_at  # unchanged — idempotent


@pytest.mark.asyncio
async def test_list_inbox_user_scoped() -> None:
    """list_inbox must only return the requesting user's notifications."""
    from app.application.services.team_service import NotificationService

    repo = FakeNotificationRepository()
    svc = NotificationService(notification_repo=repo)
    ws_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    await repo.create(_make_notification(user_a, ws_id))
    await repo.create(_make_notification(user_b, ws_id))

    page = await svc.list_inbox(user_id=user_a, workspace_id=ws_id)
    assert all(n.recipient_id == user_a for n in page.items)
    assert page.total == 1


@pytest.mark.asyncio
async def test_mark_all_read_only_for_user() -> None:
    """mark_all_read must not touch other users' notifications."""
    from app.application.services.notification_service import (
        ExtendedNotificationService,
    )

    repo = FakeNotificationRepository()
    svc = ExtendedNotificationService(notification_repo=repo)
    ws_id = uuid4()
    user_a = uuid4()
    user_b = uuid4()

    n_a = _make_notification(user_a, ws_id)
    n_b = _make_notification(user_b, ws_id)
    await repo.create(n_a)
    await repo.create(n_b)

    updated = await svc.mark_all_read(user_id=user_a, workspace_id=ws_id)
    assert updated == 1
    assert repo._store[n_b.id].state == NotificationState.UNREAD


@pytest.mark.asyncio
async def test_unread_count_returns_correct_number() -> None:
    from app.application.services.notification_service import (
        ExtendedNotificationService,
    )

    repo = FakeNotificationRepository()
    svc = ExtendedNotificationService(notification_repo=repo)
    ws_id = uuid4()
    user_id = uuid4()

    await repo.create(_make_notification(user_id, ws_id))
    await repo.create(_make_notification(user_id, ws_id))
    await repo.create(_make_notification(user_id, ws_id, state=NotificationState.READ))

    count = await svc.unread_count(user_id=user_id, workspace_id=ws_id)
    assert count == 2
