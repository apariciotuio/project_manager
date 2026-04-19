"""EP-08 — Unit tests for notification Celery tasks.

Tests run synchronously. Celery eager mode (task_always_eager=True) means
task invocations execute synchronously in-process.

Injection strategy:
  - monkeypatch `_build_fan_out_deps` to return fake service + repos
  - monkeypatch `_build_sweep_deps` similarly
  - FakeNotificationService tracks calls; FakeNotificationRepository records
    inserted rows
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.team import Notification, NotificationState

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNotificationRepo:
    def __init__(self) -> None:
        self._store: dict[str, Notification] = {}  # idempotency_key -> Notification
        self.archived: list[UUID] = []

    async def bulk_insert_idempotent(
        self, notifications: list[Notification]
    ) -> list[Notification]:
        result = []
        for n in notifications:
            if n.idempotency_key not in self._store:
                self._store[n.idempotency_key] = n
            result.append(self._store[n.idempotency_key])
        return result

    async def archive_stale(
        self, *, read_before: datetime, actioned_before: datetime, now: datetime
    ) -> dict[str, int]:
        archived_read = 0
        archived_actioned = 0
        for n in list(self._store.values()):
            if n.state == NotificationState.READ and n.read_at and n.read_at < read_before:
                n.archived_at = now  # type: ignore[attr-defined]
                archived_read += 1
            elif (
                n.state == NotificationState.ACTIONED
                and n.actioned_at
                and n.actioned_at < actioned_before
            ):
                n.archived_at = now  # type: ignore[attr-defined]
                archived_actioned += 1
        return {"archived_read": archived_read, "archived_actioned": archived_actioned}

    def all_notifications(self) -> list[Notification]:
        return list(self._store.values())


class FakeExtendedNotificationService:
    def __init__(self, repo: FakeNotificationRepo) -> None:
        self._repo = repo
        self.bulk_enqueue_calls: list[list[Notification]] = []

    async def bulk_enqueue(self, *, notifications: list[Notification]) -> list[Notification]:
        self.bulk_enqueue_calls.append(notifications)
        return await self._repo.bulk_insert_idempotent(notifications)


def _make_notification(
    *,
    recipient_id: UUID,
    workspace_id: UUID,
    subject_id: UUID,
    event_type: str,
    state: NotificationState = NotificationState.UNREAD,
    created_at: datetime | None = None,
    read_at: datetime | None = None,
    actioned_at: datetime | None = None,
) -> Notification:
    n = Notification.create(
        workspace_id=workspace_id,
        recipient_id=recipient_id,
        type=event_type,
        subject_type="work_item",
        subject_id=subject_id,
        deeplink=f"/items/{subject_id}",
        idempotency_key=f"{event_type}:{subject_id}:{recipient_id}",
    )
    n.state = state
    if created_at:
        n.created_at = created_at
    if read_at:
        n.read_at = read_at
    if actioned_at:
        n.actioned_at = actioned_at
    return n


# ---------------------------------------------------------------------------
# Commit 1 — fan_out_notification task tests
# ---------------------------------------------------------------------------


class TestFanOutNotification:
    """fan_out_notification: resolve recipients, bulk_insert, idempotency."""

    def _patch_fan_out_deps(
        self,
        monkeypatch: pytest.MonkeyPatch,
        svc: FakeExtendedNotificationService,
        recipients: list[UUID],
    ) -> None:
        import app.infrastructure.tasks.notification_tasks as mod

        async def _fake_build(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
            return {
                "svc": svc,
                "recipients": recipients,
            }

        monkeypatch.setattr(mod, "_build_fan_out_deps", _fake_build)

    def test_direct_assignment_produces_one_notification(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Single direct recipient → exactly 1 INSERT."""
        repo = FakeNotificationRepo()
        svc = FakeExtendedNotificationService(repo)
        recipient = uuid4()
        self._patch_fan_out_deps(monkeypatch, svc, [recipient])

        import app.infrastructure.tasks.notification_tasks as mod

        result = asyncio.run(
            mod._run_fan_out(
                event_type="review.requested",
                payload={
                    "workspace_id": str(uuid4()),
                    "source_id": str(uuid4()),
                    "subject_type": "review",
                    "subject_id": str(uuid4()),
                    "deeplink": "/items/x",
                    "actor_id": str(uuid4()),
                    "extra": {},
                },
                recipients=[recipient],
                svc=svc,
            )
        )
        assert result["inserted"] == 1
        assert len(repo.all_notifications()) == 1

    def test_team_assignment_produces_n_notifications(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """N recipients → N INSERTs."""
        repo = FakeNotificationRepo()
        svc = FakeExtendedNotificationService(repo)
        recipients = [uuid4(), uuid4(), uuid4()]

        workspace_id = uuid4()
        subject_id = uuid4()
        result = asyncio.run(
            mod_run_fan_out(
                svc=svc,
                recipients=recipients,
                workspace_id=workspace_id,
                subject_id=subject_id,
                event_type="review.team_assigned",
            )
        )
        assert result["inserted"] == 3
        assert len(repo.all_notifications()) == 3

    def test_idempotency_on_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Calling _run_fan_out twice with same payload inserts only once."""
        from app.infrastructure.tasks.notification_tasks import _run_fan_out

        repo = FakeNotificationRepo()
        svc = FakeExtendedNotificationService(repo)
        recipient = uuid4()
        workspace_id = uuid4()
        subject_id = uuid4()
        source_id = uuid4()  # stable ID for deterministic idempotency_key

        payload: dict[str, Any] = {
            "workspace_id": str(workspace_id),
            "source_id": str(source_id),
            "subject_type": "review",
            "subject_id": str(subject_id),
            "deeplink": f"/items/{subject_id}",
            "actor_id": None,
            "extra": {},
        }

        asyncio.run(_run_fan_out(event_type="review.requested", payload=payload, recipients=[recipient], svc=svc))
        asyncio.run(_run_fan_out(event_type="review.requested", payload=payload, recipients=[recipient], svc=svc))

        # Still only one stored row — idempotency_key collision skipped
        assert len(repo.all_notifications()) == 1

    def test_zero_recipients_inserts_nothing(self) -> None:
        """Empty recipient list → 0 inserts, no error."""
        repo = FakeNotificationRepo()
        svc = FakeExtendedNotificationService(repo)

        result = asyncio.run(
            mod_run_fan_out(
                svc=svc,
                recipients=[],
                workspace_id=uuid4(),
                subject_id=uuid4(),
                event_type="review.requested",
            )
        )
        assert result["inserted"] == 0
        assert len(repo.all_notifications()) == 0

    def test_fan_out_notification_enqueues_via_service(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """fan_out_notification calls bulk_enqueue exactly once."""
        repo = FakeNotificationRepo()
        svc = FakeExtendedNotificationService(repo)
        recipient = uuid4()
        workspace_id = uuid4()
        subject_id = uuid4()

        import app.infrastructure.tasks.notification_tasks as mod

        async def _fake_build(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
            return {"svc": svc, "recipients": [recipient]}

        monkeypatch.setattr(mod, "_build_fan_out_deps", _fake_build)

        result = asyncio.run(
            mod.fan_out_notification(
                event_type="review.requested",
                payload={
                    "workspace_id": str(workspace_id),
                    "source_id": str(uuid4()),
                    "subject_type": "review",
                    "subject_id": str(subject_id),
                    "deeplink": f"/items/{subject_id}",
                    "actor_id": None,
                    "extra": {},
                },
            )
        )
        assert result["inserted"] == 1
        assert len(svc.bulk_enqueue_calls) == 1


# ---------------------------------------------------------------------------
# Helper: _run_fan_out (called without going through Celery task wrapper)
# ---------------------------------------------------------------------------

async def mod_run_fan_out(
    *,
    svc: FakeExtendedNotificationService,
    recipients: list[UUID],
    workspace_id: UUID,
    subject_id: UUID,
    event_type: str,
) -> dict[str, int]:
    """Call the inner async logic directly so we can test it without Celery."""
    from app.infrastructure.tasks.notification_tasks import _run_fan_out

    return await _run_fan_out(
        event_type=event_type,
        payload={
            "workspace_id": str(workspace_id),
            "source_id": str(uuid4()),
            "subject_type": "work_item",
            "subject_id": str(subject_id),
            "deeplink": f"/items/{subject_id}",
            "actor_id": None,
            "extra": {},
        },
        recipients=recipients,
        svc=svc,
    )


# ---------------------------------------------------------------------------
# Commit 2 — sweep_expired_notifications task tests
# ---------------------------------------------------------------------------


class TestSweepExpiredNotifications:
    """sweep_expired_notifications: archives stale read/actioned, leaves active."""

    def _patch_sweep_deps(
        self,
        monkeypatch: pytest.MonkeyPatch,
        repo: FakeNotificationRepo,
    ) -> None:
        import app.infrastructure.tasks.notification_tasks as mod

        async def _fake_build() -> dict[str, Any]:
            return {"repo": repo}

        monkeypatch.setattr(mod, "_build_sweep_deps", _fake_build)

    def test_archives_stale_read_notifications(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read notifications > 30 days old → archived_at set."""
        repo = FakeNotificationRepo()
        old_read_at = datetime.now(UTC) - timedelta(days=31)
        n = _make_notification(
            recipient_id=uuid4(),
            workspace_id=uuid4(),
            subject_id=uuid4(),
            event_type="state_changed",
            state=NotificationState.READ,
            read_at=old_read_at,
        )
        repo._store[n.idempotency_key] = n
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        result = asyncio.run(mod._run_sweep())
        assert result["archived_read"] == 1
        assert result["archived_actioned"] == 0

    def test_archives_stale_actioned_notifications(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Actioned notifications > 90 days old → archived_at set."""
        repo = FakeNotificationRepo()
        old_actioned_at = datetime.now(UTC) - timedelta(days=91)
        n = _make_notification(
            recipient_id=uuid4(),
            workspace_id=uuid4(),
            subject_id=uuid4(),
            event_type="review.responded",
            state=NotificationState.ACTIONED,
            actioned_at=old_actioned_at,
        )
        repo._store[n.idempotency_key] = n
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        result = asyncio.run(mod._run_sweep())
        assert result["archived_actioned"] == 1
        assert result["archived_read"] == 0

    def test_leaves_active_notifications_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recent unread notifications are not archived."""
        repo = FakeNotificationRepo()
        n = _make_notification(
            recipient_id=uuid4(),
            workspace_id=uuid4(),
            subject_id=uuid4(),
            event_type="comment_added",
            state=NotificationState.UNREAD,
            created_at=datetime.now(UTC),
        )
        repo._store[n.idempotency_key] = n
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        result = asyncio.run(mod._run_sweep())
        assert result["archived_read"] == 0
        assert result["archived_actioned"] == 0
