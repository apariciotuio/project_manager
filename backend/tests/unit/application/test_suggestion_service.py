"""Unit tests for SuggestionService — EP-03 Phase 5.

Only tests generate + list_pending + update_single_status.
apply_partial is deferred to EP-04+EP-07.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import FakeAssistantSuggestionRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_suggestion(work_item_id: UUID, *, status="pending", expires_at: datetime | None = None):
    from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus

    now = datetime.now(UTC)
    if expires_at is None:
        expires_at = now + timedelta(hours=1)
    return AssistantSuggestion(
        id=uuid4(),
        workspace_id=uuid4(),
        work_item_id=work_item_id,
        thread_id=None,
        section_id=None,
        proposed_content="Proposed content",
        current_content="Current content",
        rationale="Some rationale",
        status=SuggestionStatus(status),
        version_number_target=1,
        batch_id=uuid4(),
        dundun_request_id=None,
        created_by=uuid4(),
        created_at=now,
        updated_at=now,
        expires_at=expires_at,
    )


def _make_service(suggestion_repo=None, dundun=None, callback_url="https://app/cb", now=None):
    from app.application.services.suggestion_service import SuggestionService

    if suggestion_repo is None:
        suggestion_repo = FakeAssistantSuggestionRepository()
    if dundun is None:
        dundun = FakeDundunClient()
    kwargs = {
        "suggestion_repo": suggestion_repo,
        "dundun_client": dundun,
        "callback_url": callback_url,
    }
    if now is not None:
        kwargs["now"] = now
    return SuggestionService(**kwargs)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


class TestGenerate:
    async def test_returns_uuid_batch_id(self) -> None:
        service = _make_service()
        batch_id = await service.generate(uuid4(), uuid4())
        assert isinstance(batch_id, UUID)

    async def test_invokes_wm_suggestion_agent(self) -> None:
        dundun = FakeDundunClient()
        service = _make_service(dundun=dundun)
        work_item_id = uuid4()
        user_id = uuid4()

        await service.generate(work_item_id, user_id)

        assert len(dundun.invocations) == 1
        agent, uid, _, wi_id, _, _ = dundun.invocations[0]
        assert agent == "wm_suggestion_agent"
        assert uid == user_id
        assert wi_id == work_item_id

    async def test_batch_id_included_in_payload(self) -> None:
        dundun = FakeDundunClient()
        service = _make_service(dundun=dundun)

        batch_id = await service.generate(uuid4(), uuid4())

        _, _, _, _, _, payload = dundun.invocations[0]
        assert payload["batch_id"] == str(batch_id)

    async def test_callback_url_passed_to_dundun(self) -> None:
        url = "https://myapp.io/suggestions/callback"
        dundun = FakeDundunClient()
        service = _make_service(dundun=dundun, callback_url=url)

        await service.generate(uuid4(), uuid4())

        _, _, _, _, callback, _ = dundun.invocations[0]
        assert callback == url

    async def test_no_suggestion_rows_created(self) -> None:
        """generate() does not create DB rows — that is the callback's job."""
        repo = FakeAssistantSuggestionRepository()
        service = _make_service(suggestion_repo=repo)

        batch_id = await service.generate(uuid4(), uuid4())

        rows = await repo.get_by_batch_id(batch_id)
        assert rows == []

    async def test_each_call_returns_unique_batch_id(self) -> None:
        service = _make_service()
        b1 = await service.generate(uuid4(), uuid4())
        b2 = await service.generate(uuid4(), uuid4())
        assert b1 != b2


# ---------------------------------------------------------------------------
# list_pending_for_work_item
# ---------------------------------------------------------------------------


class TestListPendingForWorkItem:
    async def test_returns_pending_suggestions(self) -> None:
        repo = FakeAssistantSuggestionRepository()
        work_item_id = uuid4()
        s1 = _make_suggestion(work_item_id, status="pending")
        s2 = _make_suggestion(work_item_id, status="pending")
        await repo.create_batch([s1, s2])

        service = _make_service(suggestion_repo=repo)
        result = await service.list_pending_for_work_item(work_item_id)

        assert len(result) == 2

    async def test_excludes_accepted_suggestions(self) -> None:
        repo = FakeAssistantSuggestionRepository()
        work_item_id = uuid4()
        pending = _make_suggestion(work_item_id, status="pending")
        accepted = _make_suggestion(work_item_id, status="accepted")
        await repo.create_batch([pending, accepted])

        service = _make_service(suggestion_repo=repo)
        result = await service.list_pending_for_work_item(work_item_id)

        ids = [s.id for s in result]
        assert pending.id in ids
        assert accepted.id not in ids

    async def test_excludes_expired_suggestions(self) -> None:
        repo = FakeAssistantSuggestionRepository()
        work_item_id = uuid4()
        expired_at = datetime.now(UTC) - timedelta(hours=1)
        expired = _make_suggestion(work_item_id, status="pending", expires_at=expired_at)
        await repo.create_batch([expired])

        service = _make_service(suggestion_repo=repo)
        result = await service.list_pending_for_work_item(work_item_id)

        assert result == []

    async def test_returns_empty_for_unknown_work_item(self) -> None:
        service = _make_service()
        result = await service.list_pending_for_work_item(uuid4())
        assert result == []


# ---------------------------------------------------------------------------
# update_single_status
# ---------------------------------------------------------------------------


class TestUpdateSingleStatus:
    async def test_accept_pending_suggestion(self) -> None:
        from app.domain.models.assistant_suggestion import SuggestionStatus

        repo = FakeAssistantSuggestionRepository()
        work_item_id = uuid4()
        s = _make_suggestion(work_item_id, status="pending")
        await repo.create_batch([s])

        service = _make_service(suggestion_repo=repo)
        updated = await service.update_single_status(s.id, SuggestionStatus.ACCEPTED)

        assert updated.status == SuggestionStatus.ACCEPTED

    async def test_reject_pending_suggestion(self) -> None:
        from app.domain.models.assistant_suggestion import SuggestionStatus

        repo = FakeAssistantSuggestionRepository()
        work_item_id = uuid4()
        s = _make_suggestion(work_item_id, status="pending")
        await repo.create_batch([s])

        service = _make_service(suggestion_repo=repo)
        updated = await service.update_single_status(s.id, SuggestionStatus.REJECTED)

        assert updated.status == SuggestionStatus.REJECTED

    async def test_accept_expired_suggestion_raises(self) -> None:
        from app.domain.exceptions import SuggestionExpiredError
        from app.domain.models.assistant_suggestion import SuggestionStatus

        repo = FakeAssistantSuggestionRepository()
        expired_at = datetime.now(UTC) - timedelta(hours=1)
        s = _make_suggestion(uuid4(), status="pending", expires_at=expired_at)
        await repo.create_batch([s])

        service = _make_service(suggestion_repo=repo)
        with pytest.raises(SuggestionExpiredError):
            await service.update_single_status(s.id, SuggestionStatus.ACCEPTED)

    async def test_accept_already_rejected_raises_invalid_state(self) -> None:
        from app.domain.exceptions import InvalidSuggestionStateError
        from app.domain.models.assistant_suggestion import SuggestionStatus

        repo = FakeAssistantSuggestionRepository()
        s = _make_suggestion(uuid4(), status="rejected")
        await repo.create_batch([s])

        service = _make_service(suggestion_repo=repo)
        with pytest.raises(InvalidSuggestionStateError):
            await service.update_single_status(s.id, SuggestionStatus.ACCEPTED)

    async def test_not_found_raises_value_error(self) -> None:
        service = _make_service()
        from app.domain.models.assistant_suggestion import SuggestionStatus

        with pytest.raises(ValueError, match="not found"):
            await service.update_single_status(uuid4(), SuggestionStatus.ACCEPTED)

    async def test_invalid_target_status_raises(self) -> None:
        from app.domain.models.assistant_suggestion import SuggestionStatus

        repo = FakeAssistantSuggestionRepository()
        s = _make_suggestion(uuid4(), status="pending")
        await repo.create_batch([s])

        service = _make_service(suggestion_repo=repo)
        with pytest.raises(ValueError):
            await service.update_single_status(s.id, SuggestionStatus.PENDING)
