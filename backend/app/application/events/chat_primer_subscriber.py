"""EP-22 — ChatPrimerSubscriber.

Listens for WorkItemCreatedEvent and primes the Dundun conversation thread
with the work item's original_input as the first user message.

Design refs: tasks/EP-22/design.md §2, tasks/EP-22/dundun-specifications.md §5.

Fire-and-forget: the EventBus swallows handler exceptions (see event_bus.py).
Creation never fails because of a Dundun outage.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.application.events.event_bus import Event
from app.application.events.events import WorkItemCreatedEvent
from app.application.services.conversation_service import ConversationService
from app.domain.ports.dundun import DundunClient
from app.domain.repositories.conversation_thread_repository import IConversationThreadRepository
from app.domain.repositories.section_repository import ISectionRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _build_sections_snapshot(sections: list[Any]) -> dict[str, str]:
    """Build { section_type: content } from a list of Section domain objects."""
    return {s.section_type.value: s.content for s in sections}


def make_chat_primer_handler(
    *,
    work_item_repo: IWorkItemRepository,
    thread_repo: IConversationThreadRepository,
    conversation_svc: ConversationService,
    dundun_client: DundunClient,
    callback_url: str,
    section_repo: ISectionRepository | None = None,
    now: Callable[[], datetime] = _utcnow,
) -> Callable[[Event], Any]:
    """Factory returning an async handler for WorkItemCreatedEvent.

    Separate from the registration function so unit tests can inject all deps
    directly without going through the DI framework.
    """

    async def handle(event: Event) -> None:
        if not isinstance(event, WorkItemCreatedEvent):
            return

        # 1. Load the work item to read original_input (Option B from design §2.3)
        work_item = await work_item_repo.get(event.work_item_id, event.workspace_id)
        if work_item is None:
            logger.warning(
                "chat_primer_subscriber: work_item_not_found event_id=%s work_item_id=%s",
                event.event_id,
                event.work_item_id,
            )
            return

        original_input = work_item.original_input
        if not original_input or not original_input.strip():
            logger.debug(
                "chat_primer_subscriber: skipping_empty_input event_id=%s work_item_id=%s",
                event.event_id,
                event.work_item_id,
            )
            # Still ensure thread exists idempotently
            await conversation_svc.get_or_create_thread(
                workspace_id=event.workspace_id,
                user_id=event.creator_id,
                work_item_id=event.work_item_id,
            )
            return

        # 2. Get/create the thread
        thread = await conversation_svc.get_or_create_thread(
            workspace_id=event.workspace_id,
            user_id=event.creator_id,
            work_item_id=event.work_item_id,
        )

        # 3. Check idempotency guard via row-lock acquire
        #    acquire_for_primer returns None if already primed or not found
        locked_thread = await thread_repo.acquire_for_primer(thread.id)
        if locked_thread is None:
            logger.debug(
                "chat_primer_subscriber: already_primed event_id=%s thread_id=%s",
                event.event_id,
                thread.id,
            )
            return

        # 4. Build sections snapshot (template defaults at creation time)
        snapshot: dict[str, str] = {}
        if section_repo is not None:
            try:
                sections = await section_repo.get_by_work_item(event.work_item_id)
                snapshot = _build_sections_snapshot(sections)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "chat_primer_subscriber: sections_snapshot_failed work_item_id=%s",
                    event.work_item_id,
                    exc_info=True,
                )

        # 5. Send primer to Dundun
        try:
            await dundun_client.invoke_agent(
                agent="chat",
                user_id=event.creator_id,
                conversation_id=thread.dundun_conversation_id,
                work_item_id=event.work_item_id,
                callback_url=callback_url,
                payload={
                    "message": original_input,
                    "caller_role": "employee",
                    "context": {
                        "sections_snapshot": snapshot,
                    },
                },
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "chat_primer_subscriber: dundun_invoke_failed "
                "event_id=%s thread_id=%s work_item_id=%s primer_length=%d",
                event.event_id,
                thread.id,
                event.work_item_id,
                len(original_input),
                exc_info=True,
            )
            # Do NOT mark primer_sent_at — allow retry on next event delivery
            return

        # 6. Persist primer_sent_at atomically
        primed_thread = locked_thread.mark_primer_sent(now())
        await thread_repo.update(primed_thread)

        logger.info(
            "chat_primer_subscriber: primer_sent "
            "event_id=%s thread_id=%s work_item_id=%s primer_length=%d dundun_status=accepted",
            event.event_id,
            thread.id,
            event.work_item_id,
            len(original_input),
        )

    return handle


def register_chat_primer_subscribers(
    bus: Any,
    work_item_repo: IWorkItemRepository,
    thread_repo: IConversationThreadRepository,
    conversation_svc: ConversationService,
    dundun_client: DundunClient,
    callback_url: str,
    section_repo: ISectionRepository | None = None,
    now: Callable[[], datetime] = _utcnow,
) -> None:
    """Register the chat primer handler on the given EventBus."""
    handler = make_chat_primer_handler(
        work_item_repo=work_item_repo,
        thread_repo=thread_repo,
        conversation_svc=conversation_svc,
        dundun_client=dundun_client,
        callback_url=callback_url,
        section_repo=section_repo,
        now=now,
    )
    bus.subscribe(WorkItemCreatedEvent, handler)
    logger.info("chat_primer_subscriber: registered handler for WorkItemCreatedEvent")
