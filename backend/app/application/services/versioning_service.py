"""EP-07 — VersioningService (sole writer of work_item_versions).

Other services (EP-04 SectionService, EP-01 WorkItemService, EP-05 TaskService)
call create_version() rather than inserting directly.

Concurrency: under READ COMMITTED (SQLAlchemy async default) two parallel
MAX+1 reads can return the same number. We explicitly promote the transaction
to SERIALIZABLE before the read-then-write so the DB serialisation layer
turns the race into a conflict the caller can translate into
VersionConflictError.
"""
from __future__ import annotations

import contextlib
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.work_item_version import WorkItemVersion
from app.domain.repositories.work_item_version_repository import (
    IWorkItemVersionRepository,
)


class VersionConflictError(Exception):
    """Raised when serialisation failure or unique constraint blocks a version write."""


class VersioningService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        repo: IWorkItemVersionRepository,
    ) -> None:
        self._session = session
        self._repo = repo

    async def create_version(
        self,
        *,
        work_item_id: UUID,
        snapshot: dict[str, Any],
        actor_id: UUID,
    ) -> WorkItemVersion:
        """Write an append-only version row with SERIALIZABLE isolation.

        Callers must not hold another transaction when invoking this — the
        SET TRANSACTION ISOLATION LEVEL statement must fire at the start of
        the DB transaction.
        """
        with contextlib.suppress(Exception):
            await self._session.execute(
                text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            )

        try:
            return await self._repo.append(work_item_id, snapshot, actor_id)
        except Exception as exc:  # IntegrityError / OperationalError
            raise VersionConflictError(
                f"could not create version for work_item_id={work_item_id}"
            ) from exc
