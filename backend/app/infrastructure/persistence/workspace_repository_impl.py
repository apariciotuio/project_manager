"""SQLAlchemy implementation of IWorkspaceRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.workspace import Workspace
from app.domain.repositories.workspace_repository import IWorkspaceRepository
from app.infrastructure.persistence.models.orm import WorkspaceORM


class WorkspaceSlugConflictError(Exception):
    """Raised when a workspace slug collides with an existing one."""


def _to_domain(row: WorkspaceORM) -> Workspace:
    return Workspace(
        id=row.id,
        name=row.name,
        slug=row.slug,
        created_by=row.created_by,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class WorkspaceRepositoryImpl(IWorkspaceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, workspace: Workspace) -> Workspace:
        row = WorkspaceORM(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            created_by=workspace.created_by,
            status=workspace.status,
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if "slug" in str(exc.orig).lower() or "workspaces_slug" in str(exc.orig).lower():
                raise WorkspaceSlugConflictError(workspace.slug) from exc
            raise
        return _to_domain(row)

    async def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        row = await self._session.get(WorkspaceORM, workspace_id)
        return _to_domain(row) if row else None

    async def get_by_slug(self, slug: str) -> Workspace | None:
        stmt = select(WorkspaceORM).where(WorkspaceORM.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def slug_exists(self, slug: str) -> bool:
        stmt = select(WorkspaceORM.id).where(WorkspaceORM.slug == slug).limit(1)
        return (await self._session.execute(stmt)).first() is not None
