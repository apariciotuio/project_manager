"""Unit tests for dundun async tasks — EP-03 Phase 6.

Tasks are now plain async functions; tests call them directly via asyncio.run().

Injection strategy: monkeypatch `app.infrastructure.tasks.dundun_tasks._build_deps`
to return FakeDundunClient + fake repos, bypassing the real DB session factory.
"""
from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import (
    FakeAssistantSuggestionRepository,
    FakeGapFindingRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_build_deps(
    monkeypatch: pytest.MonkeyPatch,
    fake_dundun: FakeDundunClient,
    suggestion_repo: FakeAssistantSuggestionRepository | None = None,
    gap_repo: FakeGapFindingRepository | None = None,
) -> None:
    """Patch the _build_deps coroutine in dundun_tasks to return fakes."""
    import app.infrastructure.tasks.dundun_tasks as tasks_module

    s_repo = suggestion_repo or FakeAssistantSuggestionRepository()
    g_repo = gap_repo or FakeGapFindingRepository()

    async def _fake_build_deps() -> dict[str, Any]:
        return {
            "dundun_client": fake_dundun,
            "suggestion_repo": s_repo,
            "gap_repo": g_repo,
        }

    monkeypatch.setattr(tasks_module, "_build_deps", _fake_build_deps)


# ---------------------------------------------------------------------------
# invoke_suggestion_agent
# ---------------------------------------------------------------------------


def test_invoke_suggestion_agent_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: calls invoke_agent once with wm_suggestion_agent, returns request_id."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_suggestion_agent

    work_item_id = str(uuid4())
    user_id = str(uuid4())
    batch_id = str(uuid4())

    result = asyncio.run(
        invoke_suggestion_agent(
            work_item_id=work_item_id,
            user_id=user_id,
            batch_id=batch_id,
        )
    )

    assert result.startswith("fake-")
    assert len(fake.invocations) == 1
    agent, uid, conv_id, wid, cb_url, payload = fake.invocations[0]
    assert agent == "wm_suggestion_agent"
    assert uid == UUID(user_id)
    assert wid == UUID(work_item_id)
    assert conv_id is None
    assert payload["batch_id"] == batch_id
    assert "/api/v1/dundun/callback" in cb_url


def test_invoke_suggestion_agent_passes_thread_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """thread_id passed as conversation_id when provided."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_suggestion_agent

    work_item_id = str(uuid4())
    user_id = str(uuid4())
    batch_id = str(uuid4())
    thread_id = str(uuid4())

    asyncio.run(
        invoke_suggestion_agent(
            work_item_id=work_item_id,
            user_id=user_id,
            batch_id=batch_id,
            thread_id=thread_id,
        )
    )

    assert len(fake.invocations) == 1
    _, _, conv_id, _, _, _ = fake.invocations[0]
    assert conv_id == thread_id


def test_invoke_suggestion_agent_idempotent_on_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Idempotency: if batch already has a dundun_request_id, skip re-invocation."""
    from datetime import UTC, datetime, timedelta

    from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus

    fake = FakeDundunClient()
    suggestion_repo = FakeAssistantSuggestionRepository()

    prior_request_id = f"prior-{uuid4()}"
    batch_id = uuid4()
    work_item_id = uuid4()
    user_id = uuid4()

    now = datetime.now(UTC)
    existing = AssistantSuggestion(
        id=uuid4(),
        workspace_id=uuid4(),
        work_item_id=work_item_id,
        thread_id=None,
        section_id=None,
        proposed_content="x",
        current_content="y",
        rationale="r",
        status=SuggestionStatus.PENDING,
        version_number_target=1,
        batch_id=batch_id,
        dundun_request_id=prior_request_id,
        created_by=user_id,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )
    suggestion_repo._by_id[existing.id] = existing

    _patch_build_deps(monkeypatch, fake, suggestion_repo=suggestion_repo)

    from app.infrastructure.tasks.dundun_tasks import invoke_suggestion_agent

    result = asyncio.run(
        invoke_suggestion_agent(
            work_item_id=str(work_item_id),
            user_id=str(user_id),
            batch_id=str(batch_id),
        )
    )

    # Must return the prior request_id without calling Dundun again
    assert result == prior_request_id
    assert len(fake.invocations) == 0


def test_invoke_suggestion_agent_raises_on_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """DundunServerError propagates to caller (caller owns retry/backoff)."""
    from app.domain.ports.dundun import DundunServerError

    fake = FakeDundunClient()

    async def _fail_build_deps() -> dict[str, Any]:
        return {
            "dundun_client": fake,
            "suggestion_repo": FakeAssistantSuggestionRepository(),
            "gap_repo": FakeGapFindingRepository(),
        }

    import app.infrastructure.tasks.dundun_tasks as tasks_module
    monkeypatch.setattr(tasks_module, "_build_deps", _fail_build_deps)

    async def _failing_invoke(**_kwargs: Any) -> dict[str, Any]:
        raise DundunServerError("server blew up")

    monkeypatch.setattr(fake, "invoke_agent", _failing_invoke)

    from app.infrastructure.tasks.dundun_tasks import invoke_suggestion_agent

    with pytest.raises(DundunServerError):
        asyncio.run(
            invoke_suggestion_agent(
                work_item_id=str(uuid4()),
                user_id=str(uuid4()),
                batch_id=str(uuid4()),
            )
        )


# ---------------------------------------------------------------------------
# invoke_gap_agent
# ---------------------------------------------------------------------------


def test_invoke_gap_agent_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: calls invoke_agent once with wm_gap_agent, returns request_id."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_gap_agent

    work_item_id = str(uuid4())
    user_id = str(uuid4())

    result = asyncio.run(
        invoke_gap_agent(
            work_item_id=work_item_id,
            user_id=user_id,
        )
    )

    assert result.startswith("fake-")
    assert len(fake.invocations) == 1
    agent, uid, _, wid, cb_url, _ = fake.invocations[0]
    assert agent == "wm_gap_agent"
    assert uid == UUID(user_id)
    assert wid == UUID(work_item_id)
    assert "/api/v1/dundun/callback" in cb_url


def test_invoke_gap_agent_correct_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gap agent payload contains work_item_id."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_gap_agent

    work_item_id = str(uuid4())
    user_id = str(uuid4())

    asyncio.run(invoke_gap_agent(work_item_id=work_item_id, user_id=user_id))

    _, _, _, _, _, payload = fake.invocations[0]
    assert payload.get("work_item_id") == work_item_id


# ---------------------------------------------------------------------------
# invoke_quick_action_agent
# ---------------------------------------------------------------------------


def test_invoke_quick_action_agent_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy path: calls invoke_agent with wm_quick_action_agent."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_quick_action_agent

    work_item_id = str(uuid4())
    user_id = str(uuid4())
    action_id = str(uuid4())

    result = asyncio.run(
        invoke_quick_action_agent(
            work_item_id=work_item_id,
            user_id=user_id,
            action_id=action_id,
            action_type="rewrite_section",
            section_id=None,
        )
    )

    assert result.startswith("fake-")
    assert len(fake.invocations) == 1
    agent, uid, _, wid, cb_url, payload = fake.invocations[0]
    assert agent == "wm_quick_action_agent"
    assert uid == UUID(user_id)
    assert wid == UUID(work_item_id)
    assert payload["action_id"] == action_id
    assert payload["action_type"] == "rewrite_section"
    assert "/api/v1/dundun/callback" in cb_url


def test_invoke_quick_action_agent_with_section_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """section_id is included in payload when provided."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_quick_action_agent

    section_id = str(uuid4())
    asyncio.run(
        invoke_quick_action_agent(
            work_item_id=str(uuid4()),
            user_id=str(uuid4()),
            action_id=str(uuid4()),
            action_type="summarize",
            section_id=section_id,
        )
    )

    _, _, _, _, _, payload = fake.invocations[0]
    assert payload.get("section_id") == section_id


def test_invoke_quick_action_agent_without_section_id(monkeypatch: pytest.MonkeyPatch) -> None:
    """section_id omitted from payload when None."""
    fake = FakeDundunClient()
    _patch_build_deps(monkeypatch, fake)

    from app.infrastructure.tasks.dundun_tasks import invoke_quick_action_agent

    asyncio.run(
        invoke_quick_action_agent(
            work_item_id=str(uuid4()),
            user_id=str(uuid4()),
            action_id=str(uuid4()),
            action_type="summarize",
            section_id=None,
        )
    )

    _, _, _, _, _, payload = fake.invocations[0]
    assert "section_id" not in payload


# ---------------------------------------------------------------------------
# SF-7 — Production guard: FakeDundunClient refused in production
# ---------------------------------------------------------------------------


def test_build_deps_raises_in_production_with_fake_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_deps raises RuntimeError when use_fake=True and app.env=production."""
    import app.infrastructure.tasks.dundun_tasks as tasks_module

    class _FakeDundunSettings:
        use_fake = True

    class _FakeAppSettings:
        env = "production"

    class _FakeSettings:
        dundun = _FakeDundunSettings()
        app = _FakeAppSettings()

    import app.config.settings as settings_module
    monkeypatch.setattr(settings_module, "get_settings", lambda: _FakeSettings())

    with pytest.raises(RuntimeError, match="FakeDundunClient not allowed in production"):
        asyncio.run(tasks_module._build_deps())
