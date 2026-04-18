"""Session lifecycle tests for fan_out_notification and _run_sweep.

Verifies that the session context manager contract is upheld:
  - commit() called on success
  - rollback() called when the body raises
  - __aexit__ (close) called in the finally path even on exception

Strategy: fake session object with spies on commit, rollback, and __aexit__.
_build_fan_out_deps / _build_sweep_deps are monkeypatched to inject the fake
session; the service/repo bodies are also faked so no real DB is touched.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.models.team import Notification

# ---------------------------------------------------------------------------
# Spy session
# ---------------------------------------------------------------------------


class SpySession:
    """Minimal async context manager that records lifecycle calls."""

    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.exited = False
        self.exit_args: tuple[Any, ...] = ()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> SpySession:
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.exited = True
        self.exit_args = (exc_type, exc_val, exc_tb)


# ---------------------------------------------------------------------------
# Fakes for fan_out_notification
# ---------------------------------------------------------------------------


class FakeNotificationRepo:
    def __init__(self) -> None:
        self._store: dict[str, Notification] = {}

    async def bulk_insert_idempotent(self, notifications: list[Notification]) -> list[Notification]:
        for n in notifications:
            if n.idempotency_key not in self._store:
                self._store[n.idempotency_key] = n
        return list(self._store.values())

    async def archive_stale(
        self, *, read_before: datetime, actioned_before: datetime, now: datetime
    ) -> dict[str, int]:
        return {"archived_read": 0, "archived_actioned": 0}


class FakeNotificationService:
    def __init__(self, repo: FakeNotificationRepo, session: SpySession) -> None:
        self._repo = repo
        self._session = session  # mirrors what production code attaches

    async def bulk_enqueue(self, *, notifications: list[Notification]) -> list[Notification]:
        return await self._repo.bulk_insert_idempotent(notifications)


class ExplodingNotificationService:
    """bulk_enqueue always raises — used to test rollback path."""

    def __init__(self, session: SpySession) -> None:
        self._session = session

    async def bulk_enqueue(self, *, notifications: list[Notification]) -> list[Notification]:
        raise RuntimeError("db write failed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fan_out_payload(*, workspace_id: UUID, subject_id: UUID, recipient_id: UUID) -> dict[str, Any]:
    return {
        "workspace_id": str(workspace_id),
        "source_id": str(uuid4()),
        "subject_type": "work_item",
        "subject_id": str(subject_id),
        "deeplink": f"/items/{subject_id}",
        "actor_id": None,
        "extra": {},
        "recipient_id": str(recipient_id),
    }


# ---------------------------------------------------------------------------
# fan_out_notification — session lifecycle
# ---------------------------------------------------------------------------


class TestFanOutSessionLifecycle:
    def _patch_fan_out_deps(
        self,
        monkeypatch: pytest.MonkeyPatch,
        svc: Any,
        recipients: list[UUID],
    ) -> None:
        import app.infrastructure.tasks.notification_tasks as mod

        async def _fake_build(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
            return {"svc": svc, "recipients": recipients}

        monkeypatch.setattr(mod, "_build_fan_out_deps", _fake_build)

    def test_fan_out_commits_session_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful fan-out → session.commit() called."""
        session = SpySession()
        repo = FakeNotificationRepo()
        svc = FakeNotificationService(repo, session)
        recipient = uuid4()
        self._patch_fan_out_deps(monkeypatch, svc, [recipient])

        import app.infrastructure.tasks.notification_tasks as mod

        asyncio.run(
            mod.fan_out_notification(
                event_type="review.requested",
                payload=_fan_out_payload(
                    workspace_id=uuid4(),
                    subject_id=uuid4(),
                    recipient_id=recipient,
                ),
            )
        )

        assert session.committed is True
        assert session.rolled_back is False

    def test_fan_out_closes_session_in_finally_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session.__aexit__ is called even on success (finally block)."""
        session = SpySession()
        repo = FakeNotificationRepo()
        svc = FakeNotificationService(repo, session)
        recipient = uuid4()
        self._patch_fan_out_deps(monkeypatch, svc, [recipient])

        import app.infrastructure.tasks.notification_tasks as mod

        asyncio.run(
            mod.fan_out_notification(
                event_type="review.requested",
                payload=_fan_out_payload(
                    workspace_id=uuid4(),
                    subject_id=uuid4(),
                    recipient_id=recipient,
                ),
            )
        )

        assert session.exited is True

    def test_fan_out_rolls_back_on_body_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When bulk_enqueue raises → session.rollback() is called, not commit()."""
        session = SpySession()
        svc = ExplodingNotificationService(session)
        recipient = uuid4()
        self._patch_fan_out_deps(monkeypatch, svc, [recipient])

        import app.infrastructure.tasks.notification_tasks as mod

        with pytest.raises(RuntimeError, match="db write failed"):
            asyncio.run(
                mod.fan_out_notification(
                    event_type="review.requested",
                    payload=_fan_out_payload(
                        workspace_id=uuid4(),
                        subject_id=uuid4(),
                        recipient_id=recipient,
                    ),
                )
            )

        assert session.rolled_back is True
        assert session.committed is False

    def test_fan_out_closes_session_in_finally_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session.__aexit__ is called even when the body raises (finally block)."""
        session = SpySession()
        svc = ExplodingNotificationService(session)
        recipient = uuid4()
        self._patch_fan_out_deps(monkeypatch, svc, [recipient])

        import app.infrastructure.tasks.notification_tasks as mod

        with pytest.raises(RuntimeError):
            asyncio.run(
                mod.fan_out_notification(
                    event_type="review.requested",
                    payload=_fan_out_payload(
                        workspace_id=uuid4(),
                        subject_id=uuid4(),
                        recipient_id=recipient,
                    ),
                )
            )

        assert session.exited is True

    def test_fan_out_no_recipients_still_commits_and_closes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero recipients path: commit + close still happen."""
        session = SpySession()
        repo = FakeNotificationRepo()
        svc = FakeNotificationService(repo, session)
        self._patch_fan_out_deps(monkeypatch, svc, [])  # no recipients

        import app.infrastructure.tasks.notification_tasks as mod

        asyncio.run(
            mod.fan_out_notification(
                event_type="review.requested",
                payload=_fan_out_payload(
                    workspace_id=uuid4(),
                    subject_id=uuid4(),
                    recipient_id=uuid4(),
                ),
            )
        )

        assert session.committed is True
        assert session.exited is True


# ---------------------------------------------------------------------------
# _run_sweep — session lifecycle
# ---------------------------------------------------------------------------


class ExplodingRepo:
    """archive_stale always raises — used to test rollback path."""

    def __init__(self, session: SpySession) -> None:
        self._session_obj = session

    async def archive_stale(
        self, *, read_before: datetime, actioned_before: datetime, now: datetime
    ) -> dict[str, int]:
        raise RuntimeError("sweep query failed")


class SuccessRepo:
    def __init__(self, session: SpySession) -> None:
        self._session_obj = session

    async def archive_stale(
        self, *, read_before: datetime, actioned_before: datetime, now: datetime
    ) -> dict[str, int]:
        return {"archived_read": 2, "archived_actioned": 1}


class TestSweepSessionLifecycle:
    def _patch_sweep_deps(
        self,
        monkeypatch: pytest.MonkeyPatch,
        repo: Any,
    ) -> None:
        import app.infrastructure.tasks.notification_tasks as mod

        async def _fake_build() -> dict[str, Any]:
            return {"repo": repo}

        monkeypatch.setattr(mod, "_build_sweep_deps", _fake_build)

    def test_sweep_commits_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Successful sweep → session.commit() called."""
        session = SpySession()
        repo = SuccessRepo(session)
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        asyncio.run(mod._run_sweep())

        assert session.committed is True
        assert session.rolled_back is False

    def test_sweep_closes_session_in_finally_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session.__aexit__ called on success (finally block)."""
        session = SpySession()
        repo = SuccessRepo(session)
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        asyncio.run(mod._run_sweep())

        assert session.exited is True

    def test_sweep_rolls_back_when_archive_stale_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """archive_stale raises → rollback, not commit."""
        session = SpySession()
        repo = ExplodingRepo(session)
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        with pytest.raises(RuntimeError, match="sweep query failed"):
            asyncio.run(mod._run_sweep())

        assert session.rolled_back is True
        assert session.committed is False

    def test_sweep_closes_session_in_finally_on_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Session.__aexit__ called even when archive_stale raises (finally block)."""
        session = SpySession()
        repo = ExplodingRepo(session)
        self._patch_sweep_deps(monkeypatch, repo)

        import app.infrastructure.tasks.notification_tasks as mod

        with pytest.raises(RuntimeError):
            asyncio.run(mod._run_sweep())

        assert session.exited is True
