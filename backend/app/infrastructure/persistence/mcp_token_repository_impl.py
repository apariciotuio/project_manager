"""SQLAlchemy implementation of IMCPTokenRepository — EP-18."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.mcp_token import MCPToken
from app.infrastructure.persistence.models.orm import MCPTokenORM


def _to_domain(row: MCPTokenORM) -> MCPToken:
    return MCPToken(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        name=row.name,
        token_hash_argon2=row.token_hash_argon2,
        lookup_key_hmac=bytes(row.lookup_key_hmac),
        scopes=list(row.scopes or []),
        created_at=row.created_at,
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        rotated_from=row.rotated_from,
    )


def _to_orm(token: MCPToken) -> MCPTokenORM:
    row = MCPTokenORM()
    row.id = token.id
    row.workspace_id = token.workspace_id
    row.user_id = token.user_id
    row.name = token.name
    row.token_hash_argon2 = token.token_hash_argon2
    row.lookup_key_hmac = token.lookup_key_hmac
    row.scopes = token.scopes
    row.created_at = token.created_at
    row.expires_at = token.expires_at
    row.last_used_at = token.last_used_at
    row.revoked_at = token.revoked_at
    row.rotated_from = token.rotated_from
    return row


class MCPTokenRepositoryImpl:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_lookup_key(self, lookup_key_hmac: bytes) -> MCPToken | None:
        stmt = select(MCPTokenORM).where(MCPTokenORM.lookup_key_hmac == lookup_key_hmac)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_by_id(self, token_id: UUID, workspace_id: UUID) -> MCPToken | None:
        stmt = select(MCPTokenORM).where(
            MCPTokenORM.id == token_id,
            MCPTokenORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def save(self, token: MCPToken) -> MCPToken:
        stmt = select(MCPTokenORM).where(MCPTokenORM.id == token.id)
        existing = (await self._session.execute(stmt)).scalar_one_or_none()
        if existing:
            existing.token_hash_argon2 = token.token_hash_argon2
            existing.lookup_key_hmac = token.lookup_key_hmac
            existing.scopes = token.scopes
            existing.expires_at = token.expires_at
            existing.last_used_at = token.last_used_at
            existing.revoked_at = token.revoked_at
            existing.rotated_from = token.rotated_from
            existing.name = token.name
            await self._session.flush()
            return _to_domain(existing)
        row = _to_orm(token)
        self._session.add(row)
        await self._session.flush()
        return token

    async def list_for_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> list[MCPToken]:
        stmt = select(MCPTokenORM).where(
            MCPTokenORM.workspace_id == workspace_id,
            MCPTokenORM.user_id == user_id,
        )
        if not include_revoked:
            stmt = stmt.where(MCPTokenORM.revoked_at.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def count_active_for_user(self, workspace_id: UUID, user_id: UUID) -> int:
        from sqlalchemy import func

        now = datetime.now(UTC)
        stmt = select(func.count()).where(  # type: ignore[call-overload]
            MCPTokenORM.workspace_id == workspace_id,
            MCPTokenORM.user_id == user_id,
            MCPTokenORM.revoked_at.is_(None),
            MCPTokenORM.expires_at > now,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()
