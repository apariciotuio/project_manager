"""AuditService unit tests — fire-and-forget contract."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.application.services.audit_service import AuditService
from tests.fakes.fake_repositories import FakeAuditRepository


async def test_log_event_persists_event() -> None:
    repo = FakeAuditRepository()
    service = AuditService(repo)
    actor = uuid4()

    await service.log_event(
        category="auth",
        action="login_success",
        actor_id=actor,
        context={"ip": "10.0.0.1"},
    )

    assert len(repo.events) == 1
    event = repo.events[0]
    assert event.category == "auth"
    assert event.action == "login_success"
    assert event.actor_id == actor
    assert event.context == {"ip": "10.0.0.1"}


async def test_log_event_swallows_repository_exception() -> None:
    """Audit failure must not propagate to the caller. Logged at ERROR level.

    caplog is unreliable here because `configure_logging` in `create_app` runs
    during other tests in the session and rewires root handlers. Attach a
    dedicated handler to the audit_service logger instead.
    """
    repo = FakeAuditRepository(explode=True)
    service = AuditService(repo)

    captured: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    audit_logger = logging.getLogger("app.application.services.audit_service")
    handler = _ListHandler(level=logging.ERROR)
    audit_logger.addHandler(handler)
    try:
        await service.log_event(
            category="auth",
            action="login_success",
            actor_id=uuid4(),
        )
    finally:
        audit_logger.removeHandler(handler)

    assert any(
        "audit log failed" in rec.getMessage() for rec in captured
    ), "audit failure must be logged at ERROR"


@pytest.mark.parametrize(
    "category,action",
    [
        ("auth", "login_success"),
        ("auth", "login_blocked_no_workspace"),
        ("auth", "logout"),
        ("auth", "superadmin_seeded"),
    ],
)
async def test_log_event_accepts_all_auth_actions(category: str, action: str) -> None:
    repo = FakeAuditRepository()
    service = AuditService(repo)
    await service.log_event(category=category, action=action)  # type: ignore[arg-type]
    assert repo.events[0].action == action
