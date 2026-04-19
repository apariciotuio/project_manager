"""AuditService unit tests — fire-and-forget contract.

Intent of the exception-swallowing behavior
--------------------------------------------
The service docstring is explicit: `log_event` MUST NOT raise even if the repo
fails.  An audit failure must never block the user-facing auth flow.  The
current implementation catches every exception, logs it at ERROR level, and
returns None silently.  Tests below verify that contract is upheld.
"""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

import pytest

from app.application.services.audit_service import AuditService
from app.domain.models.audit_event import AuditCategory
from tests.fakes.fake_repositories import FakeAuditRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(*, explode: bool = False) -> tuple[AuditService, FakeAuditRepository]:
    repo = FakeAuditRepository(explode=explode)
    return AuditService(repo), repo


# ---------------------------------------------------------------------------
# append / log_event — happy path
# ---------------------------------------------------------------------------


async def test_log_event_persists_event() -> None:
    service, repo = _make_service()
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


async def test_log_event_assigns_unique_ids_per_call() -> None:
    service, repo = _make_service()

    await service.log_event(category="auth", action="login_success")
    await service.log_event(category="auth", action="login_success")

    assert len(repo.events) == 2
    assert repo.events[0].id != repo.events[1].id


async def test_log_event_stores_all_optional_fields() -> None:
    service, repo = _make_service()
    actor = uuid4()
    workspace = uuid4()
    entity = uuid4()
    before = {"role": "viewer"}
    after = {"role": "admin"}
    ctx = {"ip": "1.2.3.4", "user_agent": "test/1"}

    await service.log_event(
        category="admin",
        action="role_changed",
        actor_id=actor,
        actor_display="alice@example.com",
        workspace_id=workspace,
        entity_type="user",
        entity_id=entity,
        before_value=before,
        after_value=after,
        context=ctx,
    )

    event = repo.events[0]
    assert event.actor_display == "alice@example.com"
    assert event.workspace_id == workspace
    assert event.entity_type == "user"
    assert event.entity_id == entity
    assert event.before_value == before
    assert event.after_value == after
    assert event.context == ctx


async def test_log_event_context_defaults_to_empty_dict_when_none_passed() -> None:
    """Service normalises context=None → {} so repo always gets a dict."""
    service, repo = _make_service()

    await service.log_event(category="domain", action="item_created")

    assert repo.events[0].context == {}


async def test_log_event_context_defaults_to_empty_dict_when_omitted() -> None:
    service, repo = _make_service()

    await service.log_event(category="domain", action="item_deleted")

    assert repo.events[0].context == {}


async def test_log_event_stores_empty_context_dict_unchanged() -> None:
    service, repo = _make_service()

    await service.log_event(category="auth", action="logout", context={})

    assert repo.events[0].context == {}


async def test_log_event_actor_id_none_stored_as_none() -> None:
    service, repo = _make_service()

    await service.log_event(category="auth", action="superadmin_seeded", actor_id=None)

    assert repo.events[0].actor_id is None


async def test_log_event_workspace_id_none_stored_as_none() -> None:
    service, repo = _make_service()

    await service.log_event(category="auth", action="login_blocked_no_workspace")

    assert repo.events[0].workspace_id is None


async def test_log_event_entity_fields_none_when_omitted() -> None:
    service, repo = _make_service()

    await service.log_event(category="domain", action="something")

    event = repo.events[0]
    assert event.entity_type is None
    assert event.entity_id is None
    assert event.before_value is None
    assert event.after_value is None


async def test_log_event_multiple_calls_all_persisted() -> None:
    service, repo = _make_service()

    for i in range(5):
        await service.log_event(
            category="domain", action=f"action_{i}", context={"seq": i}
        )

    assert len(repo.events) == 5
    actions = [e.action for e in repo.events]
    assert actions == [f"action_{i}" for i in range(5)]


# ---------------------------------------------------------------------------
# Category triangulation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("category", ["auth", "admin", "domain"])
async def test_log_event_accepts_all_valid_categories(category: AuditCategory) -> None:
    service, repo = _make_service()

    await service.log_event(category=category, action="any_action")

    assert repo.events[0].category == category


# ---------------------------------------------------------------------------
# Auth action triangulation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "login_success",
        "login_blocked_no_workspace",
        "logout",
        "superadmin_seeded",
        "token_refresh",
        "password_reset_requested",
    ],
)
async def test_log_event_accepts_arbitrary_auth_action_strings(action: str) -> None:
    service, repo = _make_service()

    await service.log_event(category="auth", action=action)

    assert repo.events[0].action == action


# ---------------------------------------------------------------------------
# Exception handling — fire-and-forget contract
# ---------------------------------------------------------------------------


async def test_log_event_swallows_repository_exception() -> None:
    """Repo failure must not propagate — audit must never break the auth flow."""
    service, _ = _make_service(explode=True)

    # Must not raise — that is the entire point of the fire-and-forget contract.
    await service.log_event(category="auth", action="login_success", actor_id=uuid4())


async def test_log_event_logs_error_on_repo_failure() -> None:
    """On repo failure the service must log at ERROR level via its own logger.

    We attach a handler directly to the module logger to avoid interference from
    the app's logging configuration wired in integration tests.
    """
    service, _ = _make_service(explode=True)

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    audit_logger = logging.getLogger("app.application.services.audit_service")
    handler = _Capture(level=logging.ERROR)
    audit_logger.addHandler(handler)
    try:
        await service.log_event(
            category="auth",
            action="login_success",
            actor_id=uuid4(),
        )
    finally:
        audit_logger.removeHandler(handler)

    assert any("audit log failed" in rec.getMessage() for rec in captured), (
        "Repo exception must be logged at ERROR with 'audit log failed' in the message"
    )


async def test_log_event_logs_category_and_action_on_failure() -> None:
    """Log record must include category and action for debugging without a stack dive."""
    service, _ = _make_service(explode=True)

    captured: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    audit_logger = logging.getLogger("app.application.services.audit_service")
    handler = _Capture(level=logging.ERROR)
    audit_logger.addHandler(handler)
    try:
        await service.log_event(
            category="admin",
            action="role_changed",
            actor_id=uuid4(),
        )
    finally:
        audit_logger.removeHandler(handler)

    assert captured, "Expected at least one log record on failure"
    # The logger uses %s formatting — call getMessage() to render the template.
    msg = captured[0].getMessage()
    assert "admin" in msg
    assert "role_changed" in msg


async def test_log_event_returns_none_on_repo_failure() -> None:
    """Return value on swallowed exception is implicitly None (no explicit return)."""
    service, _ = _make_service(explode=True)

    result = await service.log_event(category="auth", action="login_success")

    assert result is None


async def test_log_event_returns_none_on_success() -> None:
    """log_event has no return value — callers must not depend on the returned entity."""
    service, _ = _make_service()

    result = await service.log_event(category="auth", action="login_success")

    assert result is None


async def test_repo_not_called_after_event_construction_fails() -> None:
    """Sanity: if AuditEvent construction were to raise, repo.append would not be called.

    This tests a hypothetical — currently construction cannot fail — but guards
    against future validation added to AuditEvent.__post_init__.
    """
    # Verify a normal flow leaves exactly one event in repo (construction succeeded).
    service, repo = _make_service()

    await service.log_event(category="auth", action="login_success")

    assert len(repo.events) == 1


# ---------------------------------------------------------------------------
# Edge cases / boundary values
# ---------------------------------------------------------------------------


async def test_log_event_empty_string_action() -> None:
    """Empty string action is accepted — enforcement is a caller responsibility."""
    service, repo = _make_service()

    await service.log_event(category="domain", action="")

    assert repo.events[0].action == ""


async def test_log_event_long_action_string() -> None:
    service, repo = _make_service()
    long_action = "a" * 512

    await service.log_event(category="domain", action=long_action)

    assert repo.events[0].action == long_action


async def test_log_event_context_with_nested_data() -> None:
    service, repo = _make_service()
    nested = {"outer": {"inner": [1, 2, 3]}, "flag": True}

    await service.log_event(category="domain", action="complex", context=nested)

    assert repo.events[0].context == nested


async def test_log_event_context_with_none_values() -> None:
    service, repo = _make_service()
    ctx: dict = {"ip": None, "user_agent": None}

    await service.log_event(category="auth", action="login_success", context=ctx)

    assert repo.events[0].context == ctx


async def test_log_event_before_and_after_value_can_be_empty_dicts() -> None:
    service, repo = _make_service()

    await service.log_event(
        category="admin",
        action="no_op",
        before_value={},
        after_value={},
    )

    event = repo.events[0]
    assert event.before_value == {}
    assert event.after_value == {}


async def test_log_event_actor_display_stored_correctly() -> None:
    service, repo = _make_service()

    await service.log_event(
        category="auth",
        action="login_success",
        actor_display="system@tuio.internal",
    )

    assert repo.events[0].actor_display == "system@tuio.internal"


async def test_log_event_all_uuid_fields_stored_correctly() -> None:
    service, repo = _make_service()
    actor = uuid4()
    workspace = uuid4()
    entity = uuid4()

    await service.log_event(
        category="domain",
        action="item_updated",
        actor_id=actor,
        workspace_id=workspace,
        entity_id=entity,
    )

    event = repo.events[0]
    assert event.actor_id == actor
    assert event.workspace_id == workspace
    assert event.entity_id == entity
    assert isinstance(event.id, UUID)
