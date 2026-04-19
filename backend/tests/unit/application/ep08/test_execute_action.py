"""EP-08 B6.4 — Unit tests for execute_action + QuickActionDispatcher.

RED phase: tests before implementation.

Covers:
- QuickActionDispatcher.dispatch: known action type delegates to handler
- QuickActionDispatcher.dispatch: unknown action type raises ValueError
- NotificationService.execute_action: calls dispatcher, transitions to actioned
- NotificationService.execute_action: review already resolved → StaleActionError
- NotificationService.execute_action: notification not found → NotFoundError
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.team import Notification

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNotificationRepository:
    def __init__(self) -> None:
        self._store: dict = {}

    async def get(self, nid):
        return self._store.get(nid)

    async def save(self, n):
        self._store[n.id] = n
        return n

    async def create(self, n):
        self._store[n.id] = n
        return n

    async def bulk_insert_idempotent(self, ns):
        return [await self.create(n) for n in ns]

    async def get_by_idempotency_key(self, key):
        return None

    async def list_unread_for_user(self, *a, **kw):
        from app.domain.queries.page import Page
        return Page(items=[], total=0, page=1, page_size=20)

    async def list_inbox_cursor(self, *a, **kw):
        from app.infrastructure.pagination import PaginationResult
        return PaginationResult(rows=[], has_next=False, next_cursor=None)

    async def unread_count(self, *a, **kw):
        return 0

    async def mark_all_read(self, *a, **kw):
        return 0

    async def archive_stale(self, *a, **kw):
        return {"archived_read": 0, "archived_actioned": 0}


def _make_notification(
    *,
    subject_type: str = "work_item",
    quick_action: dict | None = None,
) -> Notification:
    return Notification.create(
        workspace_id=uuid4(),
        recipient_id=uuid4(),
        type="review.assigned",
        subject_type=subject_type,
        subject_id=uuid4(),
        deeplink="/items/x",
        idempotency_key=str(uuid4()),
        quick_action=quick_action,
    )


# ---------------------------------------------------------------------------
# QuickActionDispatcher tests
# ---------------------------------------------------------------------------


class TestQuickActionDispatcher:
    @pytest.mark.asyncio
    async def test_dispatch_known_action_calls_handler(self) -> None:
        from app.application.services.quick_action_dispatcher import QuickActionDispatcher

        dispatched: list[tuple] = []

        async def fake_approve(subject_id, actor_id):
            dispatched.append(("approve", subject_id, actor_id))
            return {"approved": True}

        dispatcher = QuickActionDispatcher()
        dispatcher.register("approve", fake_approve)

        subject_id = uuid4()
        actor_id = uuid4()
        result = await dispatcher.dispatch(
            action_type="approve",
            subject_id=subject_id,
            actor_id=actor_id,
        )

        assert len(dispatched) == 1
        assert dispatched[0] == ("approve", subject_id, actor_id)
        assert result == {"approved": True}

    @pytest.mark.asyncio
    async def test_dispatch_unknown_action_raises_value_error(self) -> None:
        from app.application.services.quick_action_dispatcher import QuickActionDispatcher

        dispatcher = QuickActionDispatcher()
        with pytest.raises(ValueError, match="unknown action type"):
            await dispatcher.dispatch(
                action_type="nonexistent_action",
                subject_id=uuid4(),
                actor_id=uuid4(),
            )


# ---------------------------------------------------------------------------
# NotificationService.execute_action tests
# ---------------------------------------------------------------------------


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_execute_action_transitions_to_actioned(self) -> None:
        from app.application.services.quick_action_dispatcher import QuickActionDispatcher
        from app.application.services.team_service import NotificationService

        repo = FakeNotificationRepository()
        dispatcher = QuickActionDispatcher()

        async def fake_approve(subject_id, actor_id):
            return {"approved": True}

        dispatcher.register("approve", fake_approve)

        svc = NotificationService(
            notification_repo=repo, quick_action_dispatcher=dispatcher
        )

        n = _make_notification(
            quick_action={"action": "approve", "endpoint": "/x", "method": "POST", "payload_schema": {}}
        )
        await repo.create(n)

        actor_id = uuid4()
        result = await svc.execute_action(
            notification_id=n.id,
            actor_id=actor_id,
        )

        assert result["notification"]["state"] == "actioned"

    @pytest.mark.asyncio
    async def test_execute_action_not_found_raises_error(self) -> None:
        from app.application.services.quick_action_dispatcher import QuickActionDispatcher
        from app.application.services.team_service import (
            NotificationNotFoundError,
            NotificationService,
        )

        repo = FakeNotificationRepository()
        dispatcher = QuickActionDispatcher()
        svc = NotificationService(
            notification_repo=repo, quick_action_dispatcher=dispatcher
        )

        with pytest.raises(NotificationNotFoundError):
            await svc.execute_action(
                notification_id=uuid4(),
                actor_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_execute_action_already_actioned_raises_stale_action_error(self) -> None:
        from app.application.services.quick_action_dispatcher import QuickActionDispatcher
        from app.application.services.team_service import (
            NotificationService,
            StaleActionError,
        )

        repo = FakeNotificationRepository()
        dispatcher = QuickActionDispatcher()
        svc = NotificationService(
            notification_repo=repo, quick_action_dispatcher=dispatcher
        )

        n = _make_notification(
            quick_action={"action": "approve", "endpoint": "/x", "method": "POST", "payload_schema": {}}
        )
        n.mark_actioned()
        await repo.create(n)

        with pytest.raises(StaleActionError):
            await svc.execute_action(
                notification_id=n.id,
                actor_id=uuid4(),
            )
