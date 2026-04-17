"""ConversationService — conversation thread lifecycle (pointer only) — EP-03.

History is owned by Dundun. This service manages local thread rows only:
create, archive, resurrect, list. No message persistence, no token counting.

Dundun v0.1.1 has no "create conversation" endpoint (reference_dundun_api.md).
We generate a local UUID as dundun_conversation_id and adopt Dundun's ID once
we receive one from the first chat response.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.models.conversation_thread import ConversationThread
from app.domain.ports.dundun import DundunClient
from app.domain.repositories.conversation_thread_repository import (
    IConversationThreadRepository,
)

logger = logging.getLogger(__name__)


class ThreadNotFoundError(LookupError):
    """Raised when a thread does not exist or belongs to another user.

    Same exception for both cases so IDOR-scoped callers don't leak existence.
    """


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConversationService:
    def __init__(
        self,
        *,
        thread_repo: IConversationThreadRepository,
        dundun_client: DundunClient,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._thread_repo = thread_repo
        self._dundun_client = dundun_client
        self._now = now

    async def get_or_create_thread(
        self, user_id: UUID, work_item_id: UUID | None
    ) -> ConversationThread:
        """Idempotent: returns existing active thread or creates a new one.

        Archived threads are resurrected (deleted_at cleared) rather than duplicated.
        """
        existing = await self._thread_repo.get_by_user_and_work_item(user_id, work_item_id)

        if existing is not None:
            if existing.is_archived:
                # Resurrect: clear deleted_at
                resurrected = ConversationThread(
                    id=existing.id,
                    user_id=existing.user_id,
                    work_item_id=existing.work_item_id,
                    dundun_conversation_id=existing.dundun_conversation_id,
                    last_message_preview=existing.last_message_preview,
                    last_message_at=existing.last_message_at,
                    created_at=existing.created_at,
                    deleted_at=None,
                )
                updated = await self._thread_repo.update(resurrected)
                logger.info("thread_resurrected id=%s user=%s", updated.id, user_id)
                return updated
            return existing

        # Create: Dundun v0.1.1 has no explicit "create conversation" endpoint.
        # We generate a local UUID as the conversation id; the platform will adopt
        # Dundun's own id once received from the first chat response.
        dundun_conversation_id = str(uuid4())
        now = self._now()
        thread = ConversationThread(
            id=uuid4(),
            user_id=user_id,
            work_item_id=work_item_id,
            dundun_conversation_id=dundun_conversation_id,
            last_message_preview=None,
            last_message_at=None,
            created_at=now,
            deleted_at=None,
        )
        created = await self._thread_repo.create(thread)
        logger.info("thread_created id=%s user=%s work_item=%s", created.id, user_id, work_item_id)
        return created

    async def get_thread_for_user(
        self, thread_id: UUID, user_id: UUID
    ) -> ConversationThread:
        """Return the thread only if it exists AND belongs to user_id.

        Raises ThreadNotFoundError for both missing and cross-user cases —
        controllers should never be able to distinguish.
        """
        thread = await self._thread_repo.get_by_id(thread_id)
        if thread is None or thread.user_id != user_id:
            raise ThreadNotFoundError(f"thread {thread_id} not found")
        return thread

    async def get_history(self, thread_id: UUID) -> list[dict]:  # type: ignore[type-arg]
        """Return conversation history frames from Dundun.

        Dundun v0.1.1 returns [] (no read API). When frames arrive, refreshes
        last_message_preview + last_message_at on the local row.
        """
        thread = await self._thread_repo.get_by_id(thread_id)
        if thread is None:
            raise ValueError(f"Thread {thread_id} not found")

        frames = await self._dundun_client.get_history(thread.dundun_conversation_id)
        if frames:
            last = frames[-1]
            preview: str | None = None
            content = last.get("content")
            if isinstance(content, str):
                preview = content[:200]
            updated_thread = ConversationThread(
                id=thread.id,
                user_id=thread.user_id,
                work_item_id=thread.work_item_id,
                dundun_conversation_id=thread.dundun_conversation_id,
                last_message_preview=preview,
                last_message_at=self._now(),
                created_at=thread.created_at,
                deleted_at=thread.deleted_at,
            )
            await self._thread_repo.update(updated_thread)

        return frames

    async def archive_thread(self, thread_id: UUID) -> None:
        """Soft-delete local thread row. Dundun history is preserved externally."""
        thread = await self._thread_repo.get_by_id(thread_id)
        if thread is None:
            raise ValueError(f"Thread {thread_id} not found")

        archived = thread.archive(self._now())
        await self._thread_repo.update(archived)
        logger.info("thread_archived id=%s", thread_id)

    async def list_for_user(
        self,
        user_id: UUID,
        work_item_id: UUID | None = None,
    ) -> list[ConversationThread]:
        """List active threads for a user, optionally filtered by work item."""
        return await self._thread_repo.list_for_user(
            user_id, work_item_id=work_item_id, include_archived=False
        )
