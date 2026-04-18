"""SQLAlchemy impl for IInvitationRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.invitation import Invitation
from app.domain.repositories.invitation_repository import IInvitationRepository
from app.infrastructure.persistence.models.orm import InvitationORM


def _to_domain(row: InvitationORM) -> Invitation:
    return Invitation(
        id=row.id,
        workspace_id=row.workspace_id,
        email=row.email,
        token_hash=row.token_hash,
        state=row.state,  # type: ignore[arg-type]
        context_labels=list(row.context_labels or []),
        team_ids=list(row.team_ids or []),
        initial_capabilities=list(row.initial_capabilities or []),
        created_by=row.created_by,
        expires_at=row.expires_at,
        accepted_at=row.accepted_at,
        created_at=row.created_at,
    )


class InvitationRepositoryImpl(IInvitationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, invitation: Invitation) -> Invitation:
        row = InvitationORM(
            id=invitation.id,
            workspace_id=invitation.workspace_id,
            email=invitation.email,
            token_hash=invitation.token_hash,
            state=invitation.state,
            context_labels=invitation.context_labels,
            team_ids=invitation.team_ids,
            initial_capabilities=invitation.initial_capabilities,
            created_by=invitation.created_by,
            expires_at=invitation.expires_at,
            accepted_at=invitation.accepted_at,
            created_at=invitation.created_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_id(self, invitation_id: UUID) -> Invitation | None:
        row = await self._session.get(InvitationORM, invitation_id)
        return _to_domain(row) if row else None

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        stmt = select(InvitationORM).where(InvitationORM.token_hash == token_hash).limit(1)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_active_by_email(self, workspace_id: UUID, email: str) -> Invitation | None:
        stmt = (
            select(InvitationORM)
            .where(
                InvitationORM.workspace_id == workspace_id,
                InvitationORM.email == email.lower().strip(),
                InvitationORM.state == "invited",
            )
            .order_by(InvitationORM.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def save(self, invitation: Invitation) -> Invitation:
        row = await self._session.get(InvitationORM, invitation.id)
        if row is None:
            return await self.create(invitation)
        row.token_hash = invitation.token_hash
        row.state = invitation.state
        row.context_labels = invitation.context_labels
        row.team_ids = invitation.team_ids
        row.initial_capabilities = invitation.initial_capabilities
        row.expires_at = invitation.expires_at
        row.accepted_at = invitation.accepted_at
        await self._session.flush()
        return _to_domain(row)

    async def list_for_workspace(
        self, workspace_id: UUID, *, state: str | None = None
    ) -> list[Invitation]:
        stmt = select(InvitationORM).where(InvitationORM.workspace_id == workspace_id)
        if state is not None:
            stmt = stmt.where(InvitationORM.state == state)
        stmt = stmt.order_by(InvitationORM.created_at.desc()).limit(500)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]
