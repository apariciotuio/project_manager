"""SQLAlchemy implementation of IWorkspaceMembershipRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)
from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM


def _to_domain(row: WorkspaceMembershipORM) -> WorkspaceMembership:
    return WorkspaceMembership(
        id=row.id,
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=row.role,
        state=row.state,  # type: ignore[arg-type]
        is_default=row.is_default,
        joined_at=row.joined_at,
    )


class WorkspaceMembershipRepositoryImpl(IWorkspaceMembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        row = WorkspaceMembershipORM(
            id=membership.id,
            workspace_id=membership.workspace_id,
            user_id=membership.user_id,
            role=membership.role,
            state=membership.state,
            is_default=membership.is_default,
            joined_at=membership.joined_at,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_domain(row)

    async def get_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        stmt = select(WorkspaceMembershipORM).where(
            WorkspaceMembershipORM.user_id == user_id
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(row) for row in rows]

    async def get_active_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        stmt = select(WorkspaceMembershipORM).where(
            WorkspaceMembershipORM.user_id == user_id,
            WorkspaceMembershipORM.state == "active",
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(row) for row in rows]

    async def get_for_user_and_workspace(
        self, user_id: UUID, workspace_id: UUID
    ) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembershipORM)
            .where(
                WorkspaceMembershipORM.user_id == user_id,
                WorkspaceMembershipORM.workspace_id == workspace_id,
                WorkspaceMembershipORM.state == "active",
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def get_capabilities_for(
        self, user_id: UUID, workspace_id: UUID
    ) -> list[str] | None:
        """Return the capabilities array for the (user, workspace) membership.

        Narrow read helper used by the ``require_capabilities`` FastAPI
        dependency (EP-12). Returns ``None`` when there is no active
        membership — the caller translates that into a 403.
        """
        stmt = (
            select(WorkspaceMembershipORM.capabilities)
            .where(
                WorkspaceMembershipORM.user_id == user_id,
                WorkspaceMembershipORM.workspace_id == workspace_id,
                WorkspaceMembershipORM.state == "active",
            )
            .limit(1)
        )
        caps = (await self._session.execute(stmt)).scalar_one_or_none()
        if caps is None:
            return None
        return list(caps)

    async def get_default_for_user(self, user_id: UUID) -> WorkspaceMembership | None:
        stmt = (
            select(WorkspaceMembershipORM)
            .where(
                WorkspaceMembershipORM.user_id == user_id,
                WorkspaceMembershipORM.state == "active",
                WorkspaceMembershipORM.is_default.is_(True),
            )
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None
