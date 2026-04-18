"""Unit tests for ChatPrimerSubscriber — EP-22.

RED phase: all tests fail before chat_primer_subscriber.py exists.
Uses fakes only — no DB, no HTTP, no Dundun.

8+ cases covering: happy path, empty/None/whitespace input,
already-primed guard, Dundun failure, unknown work item, duplicate event.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from tests.fakes.fake_dundun_client import FakeDundunClient
from tests.fakes.fake_repositories import (
    FakeConversationThreadRepository,
    FakeWorkItemRepository,
)

WORKSPACE_ID = uuid4()


def _fixed_clock(dt: datetime):
    return lambda: dt


def _make_work_item(_workspace_id=None, original_input="Tell me about the problem"):
    from app.domain.models.work_item import WorkItem
    from app.domain.value_objects.work_item_type import WorkItemType

    owner_id = uuid4()
    creator_id = uuid4()
    project_id = uuid4()
    item = WorkItem.create(
        title="Test work item",
        type=WorkItemType.TASK,
        owner_id=owner_id,
        creator_id=creator_id,
        project_id=project_id,
        original_input=original_input,
    )
    return item, owner_id, creator_id


def _make_event(work_item_id=None, workspace_id=None, creator_id=None):
    from app.application.events.events import WorkItemCreatedEvent
    from app.domain.value_objects.work_item_type import WorkItemType

    return WorkItemCreatedEvent(
        work_item_id=work_item_id or uuid4(),
        workspace_id=workspace_id or WORKSPACE_ID,
        type=WorkItemType.TASK,
        creator_id=creator_id or uuid4(),
        owner_id=uuid4(),
    )


def _make_handler(
    work_item_repo=None,
    thread_repo=None,
    dundun=None,
    now=None,
    callback_url="http://test/callback",
):
    from app.application.events.chat_primer_subscriber import make_chat_primer_handler
    from app.application.services.conversation_service import ConversationService

    if work_item_repo is None:
        work_item_repo = FakeWorkItemRepository()
    if thread_repo is None:
        thread_repo = FakeConversationThreadRepository()
    if dundun is None:
        dundun = FakeDundunClient()

    clock = now or (lambda: datetime.now(UTC))
    conversation_svc = ConversationService(
        thread_repo=thread_repo,
        dundun_client=dundun,
        now=clock,
    )

    return (
        make_chat_primer_handler(
            work_item_repo=work_item_repo,
            thread_repo=thread_repo,
            conversation_svc=conversation_svc,
            dundun_client=dundun,
            callback_url=callback_url,
            now=clock,
        ),
        work_item_repo,
        thread_repo,
        dundun,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatPrimerSubscriber:
    async def test_non_empty_input_sends_primer_once_and_marks_sent_at(self) -> None:
        """Happy path: original_input present → invoke_agent called once, primer_sent_at set."""
        work_item, owner_id, creator_id = _make_work_item(original_input="Build the login page")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        thread_repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()
        now_dt = datetime(2026, 4, 18, 12, 0, 0, tzinfo=UTC)

        handler, _, tr, dk = _make_handler(
            work_item_repo=work_item_repo,
            thread_repo=thread_repo,
            dundun=dundun,
            now=_fixed_clock(now_dt),
        )

        event = _make_event(
            work_item_id=work_item.id,
            workspace_id=WORKSPACE_ID,
            creator_id=creator_id,
        )

        await handler(event)

        assert len(dk.invocations) == 1
        agent, user_id, conv_id, wi_id, callback, payload = dk.invocations[0]
        assert agent == "chat"
        assert payload.get("message") == "Build the login page"

        # Thread should be primed
        threads = list(tr._by_id.values())
        assert len(threads) == 1
        assert threads[0].primer_sent_at == now_dt

    async def test_empty_original_input_skips_primer(self) -> None:
        work_item, _, creator_id = _make_work_item(original_input="")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        handler, _, tr, dk = _make_handler(
            work_item_repo=work_item_repo,
            dundun=dundun,
        )

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        await handler(event)

        assert len(dk.invocations) == 0
        threads = list(tr._by_id.values())
        assert all(t.primer_sent_at is None for t in threads)

    async def test_none_original_input_skips_primer(self) -> None:
        work_item, _, creator_id = _make_work_item(original_input=None)
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        handler, _, tr, dk = _make_handler(work_item_repo=work_item_repo, dundun=dundun)

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        await handler(event)

        assert len(dk.invocations) == 0

    async def test_whitespace_only_original_input_skips_primer(self) -> None:
        work_item, _, creator_id = _make_work_item(original_input="   \n\t  ")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        handler, _, tr, dk = _make_handler(work_item_repo=work_item_repo, dundun=dundun)

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        await handler(event)

        assert len(dk.invocations) == 0

    async def test_already_primed_thread_skips_dundun_call(self) -> None:
        """primer_sent_at already set → no second invoke."""

        work_item, _, creator_id = _make_work_item(original_input="Already primed")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        thread_repo = FakeConversationThreadRepository()
        dundun = FakeDundunClient()

        handler, _, tr, dk = _make_handler(
            work_item_repo=work_item_repo,
            thread_repo=thread_repo,
            dundun=dundun,
        )

        # First call primes
        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        await handler(event)
        assert len(dk.invocations) == 1

        # Second call (duplicate event) — primer_sent_at is now set → skip
        await handler(event)
        assert len(dk.invocations) == 1  # still 1

    async def test_dundun_failure_does_not_raise_and_primer_sent_at_not_set(self) -> None:
        """If Dundun raises, handler swallows the error; primer_sent_at NOT set."""
        from app.domain.ports.dundun import DundunServerError

        work_item, _, creator_id = _make_work_item(original_input="Some input")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        dundun.next_error = DundunServerError("Dundun unavailable")

        handler, _, tr, dk = _make_handler(work_item_repo=work_item_repo, dundun=dundun)

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        # Must not raise
        await handler(event)

        threads = list(tr._by_id.values())
        assert all(t.primer_sent_at is None for t in threads)

    async def test_unknown_work_item_id_logs_and_returns(self) -> None:
        """Work item not found → handler logs and returns without error."""
        dundun = FakeDundunClient()
        handler, _, _, dk = _make_handler(dundun=dundun)

        event = _make_event()  # work_item_id not in repo
        await handler(event)  # must not raise

        assert len(dk.invocations) == 0

    async def test_duplicate_event_results_in_exactly_one_primer(self) -> None:
        """Event bus redelivery must not duplicate the primer to Dundun."""
        work_item, _, creator_id = _make_work_item(original_input="Unique message")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        handler, _, tr, dk = _make_handler(work_item_repo=work_item_repo, dundun=dundun)

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )

        await handler(event)
        await handler(event)
        await handler(event)

        assert len(dk.invocations) == 1

    async def test_primer_carries_sections_snapshot_context(self) -> None:
        """Primer invoke_agent payload should include context.sections_snapshot."""
        work_item, _, creator_id = _make_work_item(original_input="Context aware primer")
        work_item_repo = FakeWorkItemRepository()
        work_item_repo._items[(WORKSPACE_ID, work_item.id)] = work_item

        dundun = FakeDundunClient()
        handler, _, tr, dk = _make_handler(work_item_repo=work_item_repo, dundun=dundun)

        event = _make_event(
            work_item_id=work_item.id, workspace_id=WORKSPACE_ID, creator_id=creator_id
        )
        await handler(event)

        assert len(dk.invocations) == 1
        _, _, _, _, _, payload = dk.invocations[0]
        # sections_snapshot may be {} (no sections yet) but the key must be present
        assert "context" in payload
        assert "sections_snapshot" in payload["context"]
