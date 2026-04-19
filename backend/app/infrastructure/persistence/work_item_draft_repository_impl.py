"""SQLAlchemy implementation of IWorkItemDraftRepository — EP-02."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import DraftForbiddenError, WorkItemDraftNotFoundError
from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.repositories.work_item_draft_repository import IWorkItemDraftRepository
from app.domain.value_objects.draft_conflict import DraftConflict
from app.infrastructure.persistence.models.orm import WorkItemDraftORM


def _to_domain(row: WorkItemDraftORM) -> WorkItemDraft:
    return WorkItemDraft(
        id=row.id,
        user_id=row.user_id,
        workspace_id=row.workspace_id,
        data=dict(row.data) if row.data else {},
        local_version=row.local_version,
        incomplete=row.incomplete,
        created_at=row.created_at,
        updated_at=row.updated_at,
        expires_at=row.expires_at,
    )


class WorkItemDraftRepositoryImpl(IWorkItemDraftRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, draft: WorkItemDraft, expected_version: int
    ) -> WorkItemDraft | DraftConflict:
        # Check if a row already exists for this user+workspace
        stmt = select(WorkItemDraftORM).where(
            WorkItemDraftORM.user_id == draft.user_id,
            WorkItemDraftORM.workspace_id == draft.workspace_id,
        )
        existing = (await self._session.execute(stmt)).scalar_one_or_none()

        if existing is not None:
            # Optimistic lock: if server version is ahead, return conflict
            if existing.local_version > expected_version:
                return DraftConflict(
                    server_version=existing.local_version,
                    server_data=dict(existing.data) if existing.data else {},
                )
            # Update existing row, increment version
            now = datetime.now(UTC)
            from datetime import timedelta
            await self._session.execute(
                update(WorkItemDraftORM)
                .where(WorkItemDraftORM.id == existing.id)
                .values(
                    data=draft.data,
                    local_version=existing.local_version + 1,
                    incomplete=draft.incomplete,
                    updated_at=now,
                    expires_at=now + timedelta(days=30),
                )
            )
            await self._session.flush()
            # Re-fetch to get updated row
            result = (
                await self._session.execute(
                    select(WorkItemDraftORM).where(WorkItemDraftORM.id == existing.id)
                )
            ).scalar_one()
            return _to_domain(result)
        else:
            # Insert new row
            from datetime import timedelta
            now = datetime.now(UTC)
            row = WorkItemDraftORM()
            row.id = draft.id
            row.user_id = draft.user_id
            row.workspace_id = draft.workspace_id
            row.data = draft.data  # type: ignore[assignment]
            row.local_version = 1
            row.incomplete = draft.incomplete
            row.created_at = now
            row.updated_at = now
            row.expires_at = now + timedelta(days=30)
            self._session.add(row)
            await self._session.flush()
            return _to_domain(row)

    async def get_by_user_workspace(
        self, user_id: UUID, workspace_id: UUID
    ) -> WorkItemDraft | None:
        stmt = select(WorkItemDraftORM).where(
            WorkItemDraftORM.user_id == user_id,
            WorkItemDraftORM.workspace_id == workspace_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_domain(row) if row else None

    async def delete(self, draft_id: UUID, user_id: UUID) -> None:
        stmt = select(WorkItemDraftORM).where(WorkItemDraftORM.id == draft_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise WorkItemDraftNotFoundError(draft_id)
        if row.user_id != user_id:
            raise DraftForbiddenError(user_id, draft_id)
        await self._session.delete(row)
        await self._session.flush()

    async def get_expired(self) -> list[WorkItemDraft]:
        now = datetime.now(UTC)
        stmt = select(WorkItemDraftORM).where(WorkItemDraftORM.expires_at < now)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_domain(r) for r in rows]

    async def delete_expired(self) -> int:
        now = datetime.now(UTC)
        stmt = delete(WorkItemDraftORM).where(WorkItemDraftORM.expires_at < now)
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount  # type: ignore[return-value]
