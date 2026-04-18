"""IConversationThreadRepository — domain-layer interface for conversation thread persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.conversation_thread import ConversationThread


class IConversationThreadRepository(ABC):
    @abstractmethod
    async def create(self, thread: ConversationThread) -> ConversationThread:
        """Persist a new thread. Raises IntegrityError on duplicate (user_id, work_item_id)."""

    @abstractmethod
    async def get_by_id(self, thread_id: UUID) -> ConversationThread | None:
        """Return thread by primary key or None."""

    @abstractmethod
    async def get_by_user_and_work_item(
        self, user_id: UUID, work_item_id: UUID | None
    ) -> ConversationThread | None:
        """Return the unique thread for (user, work_item).

        When ``work_item_id`` is None, returns the user's general (no-item) thread.
        """

    @abstractmethod
    async def get_by_dundun_conversation_id(
        self, dundun_conversation_id: str
    ) -> ConversationThread | None:
        """Lookup by the unique Dundun conversation identifier."""

    @abstractmethod
    async def list_for_user(
        self,
        user_id: UUID,
        work_item_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list[ConversationThread]:
        """List threads owned by user.

        Optionally filter by work_item_id. By default excludes archived (deleted_at IS NOT NULL).
        """

    @abstractmethod
    async def update(self, thread: ConversationThread) -> ConversationThread:
        """Persist mutations on an existing thread (preview, archive, primer_sent_at).

        Returns updated entity.
        """

    @abstractmethod
    async def acquire_for_primer(self, thread_id: UUID) -> ConversationThread | None:
        """Row-locked SELECT WHERE primer_sent_at IS NULL.

        Returns the thread if it exists and has not yet been primed (primer_sent_at IS NULL).
        Returns None if the thread does not exist or is already primed.
        Caller must be inside an open transaction; the lock is released on commit/rollback.
        """
