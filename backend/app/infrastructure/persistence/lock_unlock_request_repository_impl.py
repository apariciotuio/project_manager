"""EP-17 — LockUnlockRequest repository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.lock_unlock_request import LockUnlockRequest
from app.infrastructure.persistence.models.orm import LockUnlockRequestORM


def _to_domain(row: LockUnlockRequestORM) -> LockUnlockRequest:
    return LockUnlockRequest(
        id=row.id,
        section_id=row.section_id,
        requester_id=row.requester_id,
        reason=row.reason,
        created_at=row.created_at,
        responded_at=row.responded_at,
        response=row.response,  # type: ignore[arg-type]
        response_note=row.response_note,
    )


class LockUnlockRequestRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, request: LockUnlockRequest) -> LockUnlockRequest:
        existing = await self._session.get(LockUnlockRequestORM, request.id)
        if existing is None:
            orm = LockUnlockRequestORM(
                id=request.id,
                section_id=request.section_id,
                requester_id=request.requester_id,
                reason=request.reason,
                created_at=request.created_at,
                responded_at=request.responded_at,
                response=request.response,
                response_note=request.response_note,
            )
            self._session.add(orm)
        else:
            existing.responded_at = request.responded_at
            existing.response = request.response
            existing.response_note = request.response_note
        await self._session.flush()
        return request

    async def get(self, request_id: UUID) -> LockUnlockRequest | None:
        stmt = select(LockUnlockRequestORM).where(LockUnlockRequestORM.id == request_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None
