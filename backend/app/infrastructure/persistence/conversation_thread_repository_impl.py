"""SQLAlchemy implementation of IConversationThreadRepository — EP-03."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.conversation_thread import ConversationThread
from app.domain.repositories.conversation_thread_repository import IConversationThreadRepository
from app.infrastructure.persistence.mappers.conversation_thread_mapper import (
    to_domain,
    to_orm,
)
from app.infrastructure.persistence.models.orm import ConversationThreadORM

_FOR_UPDATE = True


class ConversationThreadRepositoryImpl(IConversationThreadRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, thread: ConversationThread) -> ConversationThread:
        row = to_orm(thread)
        self._session.add(row)
        await self._session.flush()
        return to_domain(row)

    async def get_by_id(self, thread_id: UUID) -> ConversationThread | None:
        stmt = select(ConversationThreadORM).where(ConversationThreadORM.id == thread_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_domain(row) if row else None

    async def get_by_user_and_work_item(
        self, user_id: UUID, work_item_id: UUID | None
    ) -> ConversationThread | None:
        if work_item_id is None:
            stmt = select(ConversationThreadORM).where(
                ConversationThreadORM.user_id == user_id,
                ConversationThreadORM.work_item_id.is_(None),
            )
        else:
            stmt = select(ConversationThreadORM).where(
                ConversationThreadORM.user_id == user_id,
                ConversationThreadORM.work_item_id == work_item_id,
            )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_domain(row) if row else None

    async def get_by_dundun_conversation_id(
        self, dundun_conversation_id: str
    ) -> ConversationThread | None:
        stmt = select(ConversationThreadORM).where(
            ConversationThreadORM.dundun_conversation_id == dundun_conversation_id
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_domain(row) if row else None

    async def list_for_user(
        self,
        user_id: UUID,
        work_item_id: UUID | None = None,
        include_archived: bool = False,
    ) -> list[ConversationThread]:
        stmt = select(ConversationThreadORM).where(ConversationThreadORM.user_id == user_id)
        if work_item_id is not None:
            stmt = stmt.where(ConversationThreadORM.work_item_id == work_item_id)
        if not include_archived:
            stmt = stmt.where(ConversationThreadORM.deleted_at.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_domain(r) for r in rows]

    async def update(self, thread: ConversationThread) -> ConversationThread:
        stmt = (
            update(ConversationThreadORM)
            .where(ConversationThreadORM.id == thread.id)
            .values(
                last_message_preview=thread.last_message_preview,
                last_message_at=thread.last_message_at,
                deleted_at=thread.deleted_at,
                primer_sent_at=thread.primer_sent_at,
            )
            .returning(ConversationThreadORM)
        )
        row = (await self._session.execute(stmt)).scalar_one()
        return to_domain(row)

    async def acquire_for_primer(self, thread_id: UUID) -> ConversationThread | None:
        """Row-locked SELECT for primer idempotency.

        Returns the thread only if primer_sent_at IS NULL (not yet primed).
        Returns None if the thread does not exist OR is already primed.
        The FOR UPDATE lock serialises concurrent primer invocations.
        Caller must hold a transaction that is committed or rolled back to release the lock.
        """
        stmt = (
            select(ConversationThreadORM)
            .where(
                ConversationThreadORM.id == thread_id,
                ConversationThreadORM.primer_sent_at.is_(None),
            )
            .with_for_update()
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_domain(row) if row else None
