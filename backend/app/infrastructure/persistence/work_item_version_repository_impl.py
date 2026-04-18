"""EP-07 — SQLAlchemy implementation of IWorkItemVersionRepository.

Workspace scoping: work_item_versions has no workspace_id column (EP-04 base
table). Scoping is enforced by JOINing through work_items ON work_items.id =
work_item_versions.work_item_id AND work_items.workspace_id = :workspace_id.

Returns None on workspace mismatch — never 403 — to avoid existence disclosure.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)
from app.domain.repositories.work_item_version_repository import (
    IWorkItemVersionRepository,
)
from app.infrastructure.persistence.mappers.version_mapper import version_to_domain
from app.infrastructure.persistence.models.orm import WorkItemORM, WorkItemVersionORM


class WorkItemVersionRepositoryImpl(IWorkItemVersionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        work_item_id: UUID,
        snapshot: dict[str, Any],
        created_by: UUID,
        *,
        trigger: str = "content_edit",
        actor_type: str = "human",
        actor_id: UUID | None = None,
        commit_message: str | None = None,
    ) -> WorkItemVersion:
        """Insert a new version row under SERIALIZABLE isolation.

        The caller (VersioningService) is responsible for having already called
        SET TRANSACTION ISOLATION LEVEL SERIALIZABLE before calling this method.

        MAX+1 under SERIALIZABLE is safe: if two concurrent transactions both
        read the same MAX, one will be serialised after the other and will see
        a conflict that propagates as a UNIQUE constraint violation.
        """
        max_q = await self._session.execute(
            select(func.coalesce(func.max(WorkItemVersionORM.version_number), 0)).where(
                WorkItemVersionORM.work_item_id == work_item_id
            )
        )
        next_number: int = (max_q.scalar() or 0) + 1

        # Resolve workspace_id — work_item_id FK guarantees the row exists
        wi_row = await self._session.get(WorkItemORM, work_item_id)
        if wi_row is None:
            raise ValueError(f"work_item {work_item_id} not found")
        workspace_id = wi_row.workspace_id

        row = WorkItemVersionORM()
        row.id = uuid4()
        row.work_item_id = work_item_id
        row.workspace_id = workspace_id
        row.version_number = next_number
        row.snapshot = snapshot
        row.created_by = created_by
        row.created_at = datetime.now(UTC)
        row.snapshot_schema_version = 1
        row.trigger = trigger
        row.actor_type = actor_type
        row.actor_id = actor_id
        row.commit_message = commit_message
        row.archived = False

        self._session.add(row)
        await self._session.flush()
        return version_to_domain(row)

    async def get_latest(self, work_item_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        stmt = (
            select(WorkItemVersionORM)
            .join(WorkItemORM, WorkItemORM.id == WorkItemVersionORM.work_item_id)
            .where(
                WorkItemVersionORM.work_item_id == work_item_id,
                WorkItemORM.workspace_id == workspace_id,
            )
            .order_by(WorkItemVersionORM.version_number.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return version_to_domain(row) if row else None

    async def get(self, version_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        stmt = (
            select(WorkItemVersionORM)
            .join(WorkItemORM, WorkItemORM.id == WorkItemVersionORM.work_item_id)
            .where(
                WorkItemVersionORM.id == version_id,
                WorkItemORM.workspace_id == workspace_id,
            )
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return version_to_domain(row) if row else None

    async def get_by_number(
        self, work_item_id: UUID, version_number: int, workspace_id: UUID
    ) -> WorkItemVersion | None:
        stmt = (
            select(WorkItemVersionORM)
            .join(WorkItemORM, WorkItemORM.id == WorkItemVersionORM.work_item_id)
            .where(
                WorkItemVersionORM.work_item_id == work_item_id,
                WorkItemVersionORM.version_number == version_number,
                WorkItemORM.workspace_id == workspace_id,
            )
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return version_to_domain(row) if row else None

    async def list_by_work_item(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 20,
        before_version: int | None = None,
    ) -> list[WorkItemVersion]:
        stmt = (
            select(WorkItemVersionORM)
            .join(WorkItemORM, WorkItemORM.id == WorkItemVersionORM.work_item_id)
            .where(
                WorkItemVersionORM.work_item_id == work_item_id,
                WorkItemORM.workspace_id == workspace_id,
            )
        )
        if not include_archived:
            stmt = stmt.where(WorkItemVersionORM.archived.is_(False))
        if before_version is not None:
            stmt = stmt.where(WorkItemVersionORM.version_number < before_version)

        stmt = stmt.order_by(WorkItemVersionORM.version_number.desc()).limit(limit)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [version_to_domain(r) for r in rows]
