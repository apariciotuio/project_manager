"""SQLAlchemy implementation of ISessionRepository."""

from __future__ import annotations

from datetime import datetime, timezone, UTC
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.session import Session
from app.domain.repositories.session_repository import ISessionRepository
from app.infrastructure.persistence.models.orm import SessionORM


def _to_domain(row: SessionORM) -> Session:
    return Session(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        ip_address=str(row.ip_address) if row.ip_address is not None else None,
        user_agent=row.user_agent,
        created_at=row.created_at,
    )


class SessionRepositoryImpl(ISessionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, session: Session) -> Session:
        row = SessionORM(
            id=session.id,
            user_id=session.user_id,
            token_hash=session.token_hash,
            expires_at=session.expires_at,
            revoked_at=session.revoked_at,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            created_at=session.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        stmt = select(SessionORM).where(
            SessionORM.token_hash == token_hash,
            SessionORM.revoked_at.is_(None),
            SessionORM.expires_at > func.now(),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def revoke(self, session_id: UUID) -> None:
        stmt = (
            update(SessionORM)
            .where(SessionORM.id == session_id, SessionORM.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def delete_expired(self) -> int:
        stmt = delete(SessionORM).where(
            SessionORM.expires_at < datetime.now(UTC)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
