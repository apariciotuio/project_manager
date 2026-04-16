"""SQLAlchemy implementation of IOAuthStateRepository.

Single-use consumption via `DELETE ... RETURNING ...` — atomic on Postgres.
No race between "validate state exists" and "delete", so a duplicate callback from
the browser can never succeed twice.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.oauth_state_repository import (
    ConsumedOAuthState,
    IOAuthStateRepository,
    OAuthStateCollisionError,
)
from app.infrastructure.persistence.models.orm import OAuthStateORM


class OAuthStateRepositoryImpl(IOAuthStateRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        state: str,
        verifier: str,
        ttl_seconds: int,
        return_to: str | None = None,
        last_chosen_workspace_id: UUID | None = None,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        stmt = insert(OAuthStateORM).values(
            state=state,
            verifier=verifier,
            expires_at=expires_at,
            return_to=return_to,
            last_chosen_workspace_id=last_chosen_workspace_id,
        )
        try:
            await self._session.execute(stmt)
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            raise OAuthStateCollisionError(
                f"duplicate oauth state PK: {state!r}"
            ) from exc

    async def consume(self, state: str) -> ConsumedOAuthState | None:
        stmt = (
            delete(OAuthStateORM)
            .where(OAuthStateORM.state == state, OAuthStateORM.expires_at > func.now())
            .returning(
                OAuthStateORM.verifier,
                OAuthStateORM.return_to,
                OAuthStateORM.last_chosen_workspace_id,
            )
        )
        row = (await self._session.execute(stmt)).one_or_none()
        await self._session.flush()
        if row is None:
            return None
        return ConsumedOAuthState(
            verifier=row[0],
            return_to=row[1],
            last_chosen_workspace_id=row[2],
        )

    async def cleanup_expired(self) -> int:
        stmt = delete(OAuthStateORM).where(OAuthStateORM.expires_at < func.now())
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount or 0
