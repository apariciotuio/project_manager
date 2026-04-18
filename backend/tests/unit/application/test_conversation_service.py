"""Unit tests for ConversationService — EP-03 Phase 5.

Uses fake thread repo and fake Dundun. No DB, no HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import FakeConversationThreadRepository

# Shared workspace UUID used across all service call-sites. RLS is already
# exercised at the repo-level integration tests; here we only need a stable
# UUID to pass through the new workspace-scoped signature.
WORKSPACE_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fixed_clock(dt: datetime):
    def _now() -> datetime:
        return dt

    return _now


def _make_service(thread_repo=None, dundun=None, now=None):
    from app.application.services.conversation_service import ConversationService

    if thread_repo is None:
        thread_repo = FakeConversationThreadRepository()
    if dundun is None:
        dundun = FakeDundunClient()
    kwargs = {"thread_repo": thread_repo, "dundun_client": dundun}
    if now is not None:
        kwargs["now"] = now
    return ConversationService(**kwargs)


# ---------------------------------------------------------------------------
# get_or_create_thread — idempotency
# ---------------------------------------------------------------------------


class TestGetOrCreateThread:
    async def test_creates_thread_on_first_call(self) -> None:
        from app.domain.models.conversation_thread import ConversationThread

        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()
        work_item_id = uuid4()

        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, work_item_id)

        assert isinstance(thread, ConversationThread)
        assert thread.user_id == user_id
        assert thread.work_item_id == work_item_id
        assert thread.dundun_conversation_id is not None
        assert thread.deleted_at is None

    async def test_idempotent_second_call_returns_same_thread(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()
        work_item_id = uuid4()

        t1 = await service.get_or_create_thread(WORKSPACE_ID, user_id, work_item_id)
        t2 = await service.get_or_create_thread(WORKSPACE_ID, user_id, work_item_id)

        assert t1.id == t2.id
        assert t1.dundun_conversation_id == t2.dundun_conversation_id
        # Only one row exists
        rows = await repo.list_for_user(user_id, include_archived=True)
        assert len(rows) == 1

    async def test_different_work_items_produce_different_threads(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()

        t1 = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())
        t2 = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())

        assert t1.id != t2.id

    async def test_archived_thread_is_resurrected(self) -> None:
        repo = FakeConversationThreadRepository()
        now = datetime.now(UTC)
        service = _make_service(thread_repo=repo, now=_fixed_clock(now))
        user_id = uuid4()
        work_item_id = uuid4()

        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, work_item_id)
        await service.archive_thread(thread.id)

        # Verify it's archived
        archived = await repo.get_by_id(thread.id)
        assert archived is not None
        assert archived.deleted_at is not None

        # Resurrect via get_or_create
        resurrected = await service.get_or_create_thread(WORKSPACE_ID, user_id, work_item_id)

        assert resurrected.id == thread.id
        assert resurrected.deleted_at is None

    async def test_general_thread_with_no_work_item(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()

        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, None)

        assert thread.work_item_id is None
        assert thread.is_general_thread is True


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    async def test_delegates_to_dundun_get_history(self) -> None:
        repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        service = _make_service(thread_repo=repo, dundun=dundun)
        user_id = uuid4()

        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, None)
        conv_id = thread.dundun_conversation_id
        dundun.history_by_conversation[conv_id] = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]

        frames = await service.get_history(thread.id)

        assert len(frames) == 2
        assert frames[0]["role"] == "user"

    async def test_empty_history_returns_empty_list(self) -> None:
        repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        service = _make_service(thread_repo=repo, dundun=dundun)

        thread = await service.get_or_create_thread(WORKSPACE_ID, uuid4(), None)
        frames = await service.get_history(thread.id)

        assert frames == []

    async def test_history_refreshes_last_message_preview(self) -> None:
        repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        now = datetime.now(UTC)
        service = _make_service(thread_repo=repo, dundun=dundun, now=_fixed_clock(now))

        thread = await service.get_or_create_thread(WORKSPACE_ID, uuid4(), None)
        conv_id = thread.dundun_conversation_id
        dundun.history_by_conversation[conv_id] = [{"role": "assistant", "content": "final answer"}]

        await service.get_history(thread.id)

        stored = await repo.get_by_id(thread.id)
        assert stored is not None
        assert stored.last_message_preview == "final answer"
        assert stored.last_message_at == now

    async def test_not_found_thread_raises(self) -> None:
        service = _make_service()
        with pytest.raises(ValueError, match="not found"):
            await service.get_history(uuid4())


# ---------------------------------------------------------------------------
# archive_thread
# ---------------------------------------------------------------------------


class TestArchiveThread:
    async def test_sets_deleted_at(self) -> None:
        repo = FakeConversationThreadRepository()
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        service = _make_service(thread_repo=repo, now=_fixed_clock(now))

        thread = await service.get_or_create_thread(WORKSPACE_ID, uuid4(), None)
        await service.archive_thread(thread.id)

        stored = await repo.get_by_id(thread.id)
        assert stored is not None
        assert stored.deleted_at == now

    async def test_archive_does_not_call_dundun(self) -> None:
        repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        service = _make_service(thread_repo=repo, dundun=dundun)

        thread = await service.get_or_create_thread(WORKSPACE_ID, uuid4(), None)
        await service.archive_thread(thread.id)

        # No Dundun calls from archive
        assert len(dundun.invocations) == 0

    async def test_archive_not_found_raises(self) -> None:
        service = _make_service()
        with pytest.raises(ValueError, match="not found"):
            await service.archive_thread(uuid4())

    async def test_already_archived_stays_archived(self) -> None:
        repo = FakeConversationThreadRepository()
        now = datetime.now(UTC)
        service = _make_service(thread_repo=repo, now=_fixed_clock(now))

        thread = await service.get_or_create_thread(WORKSPACE_ID, uuid4(), None)
        await service.archive_thread(thread.id)
        await service.archive_thread(thread.id)  # idempotent

        stored = await repo.get_by_id(thread.id)
        assert stored is not None
        assert stored.deleted_at is not None


# ---------------------------------------------------------------------------
# list_for_user
# ---------------------------------------------------------------------------


class TestListForUser:
    async def test_excludes_archived_by_default(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()

        t1 = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())
        t2 = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())
        await service.archive_thread(t2.id)

        threads = await service.list_for_user(user_id)

        ids = [t.id for t in threads]
        assert t1.id in ids
        assert t2.id not in ids

    async def test_returns_empty_for_unknown_user(self) -> None:
        service = _make_service()
        threads = await service.list_for_user(uuid4())
        assert threads == []

    async def test_filters_by_work_item_id(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()
        wi_id = uuid4()

        await service.get_or_create_thread(WORKSPACE_ID, user_id, wi_id)
        await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())  # other item

        threads = await service.list_for_user(user_id, work_item_id=wi_id)

        assert len(threads) == 1
        assert threads[0].work_item_id == wi_id


class TestGetThreadForUser:
    """SEC-AUTH-001: service enforces user_id AND workspace_id scope."""

    async def test_returns_thread_when_user_and_workspace_match(self) -> None:
        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()
        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())

        got = await service.get_thread_for_user(thread.id, user_id, WORKSPACE_ID)
        assert got.id == thread.id

    async def test_raises_not_found_when_thread_missing(self) -> None:
        from app.application.services.conversation_service import ThreadNotFoundError

        service = _make_service()
        with pytest.raises(ThreadNotFoundError):
            await service.get_thread_for_user(uuid4(), uuid4(), WORKSPACE_ID)

    async def test_raises_not_found_for_cross_user_access(self) -> None:
        from app.application.services.conversation_service import ThreadNotFoundError

        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        owner_id = uuid4()
        attacker_id = uuid4()
        thread = await service.get_or_create_thread(WORKSPACE_ID, owner_id, uuid4())

        with pytest.raises(ThreadNotFoundError):
            await service.get_thread_for_user(thread.id, attacker_id, WORKSPACE_ID)

    async def test_raises_not_found_for_cross_workspace_access(self) -> None:
        """Same user, different workspace_id in the caller's scope → NOT FOUND.

        Prevents a multi-workspace user from accessing threads from another
        workspace via a stale/switched JWT workspace_id.
        """
        from app.application.services.conversation_service import ThreadNotFoundError

        repo = FakeConversationThreadRepository()
        service = _make_service(thread_repo=repo)
        user_id = uuid4()
        other_workspace = uuid4()
        thread = await service.get_or_create_thread(WORKSPACE_ID, user_id, uuid4())

        with pytest.raises(ThreadNotFoundError):
            await service.get_thread_for_user(thread.id, user_id, other_workspace)
