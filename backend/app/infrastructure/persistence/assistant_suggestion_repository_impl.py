"""SQLAlchemy implementation of IAssistantSuggestionRepository — EP-03."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.domain.repositories.assistant_suggestion_repository import (
    IAssistantSuggestionRepository,
)
from app.infrastructure.persistence.mappers.assistant_suggestion_mapper import (
    to_domain,
    to_orm,
)
from app.infrastructure.persistence.models.orm import AssistantSuggestionORM


class AssistantSuggestionRepositoryImpl(IAssistantSuggestionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_batch(
        self, suggestions: list[AssistantSuggestion]
    ) -> list[AssistantSuggestion]:
        if not suggestions:
            return []
        rows = [to_orm(s) for s in suggestions]
        for row in rows:
            self._session.add(row)
        await self._session.flush()
        return [to_domain(r) for r in rows]

    async def get_by_id(self, suggestion_id: UUID) -> AssistantSuggestion | None:
        stmt = select(AssistantSuggestionORM).where(AssistantSuggestionORM.id == suggestion_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_domain(row) if row else None

    async def get_by_batch_id(self, batch_id: UUID) -> list[AssistantSuggestion]:
        stmt = select(AssistantSuggestionORM).where(AssistantSuggestionORM.batch_id == batch_id)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_domain(r) for r in rows]

    async def get_by_dundun_request_id(self, dundun_request_id: str) -> list[AssistantSuggestion]:
        stmt = select(AssistantSuggestionORM).where(
            AssistantSuggestionORM.dundun_request_id == dundun_request_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_domain(r) for r in rows]

    async def list_pending_for_work_item(self, work_item_id: UUID) -> list[AssistantSuggestion]:
        from datetime import UTC

        now = datetime.now(UTC)
        stmt = select(AssistantSuggestionORM).where(
            AssistantSuggestionORM.work_item_id == work_item_id,
            AssistantSuggestionORM.status == SuggestionStatus.PENDING.value,
            AssistantSuggestionORM.expires_at > now,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [to_domain(r) for r in rows]

    async def update_status(
        self,
        ids: list[UUID],
        status: SuggestionStatus,
        now: datetime,
    ) -> int:
        if not ids:
            return 0
        stmt = (
            update(AssistantSuggestionORM)
            .where(AssistantSuggestionORM.id.in_(ids))
            .values(status=status.value, updated_at=now)
        )
        cursor = await self._session.execute(stmt)
        await self._session.flush()
        return int(cast(CursorResult[tuple[object, ...]], cursor).rowcount)
