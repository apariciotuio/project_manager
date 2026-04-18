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
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.work_item_version import (
    VersionActorType,
    VersionTrigger,
    WorkItemVersion,
)
from app.domain.repositories.section_repository import ISectionRepository
from app.domain.repositories.task_node_repository import ITaskNodeRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.domain.repositories.work_item_version_repository import (
    IWorkItemVersionRepository,
)

logger = logging.getLogger(__name__)


class VersionConflictError(Exception):
    """Raised when serialisation failure or unique constraint blocks a version write."""


class VersioningService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        repo: IWorkItemVersionRepository,
        work_item_repo: IWorkItemRepository | None = None,
        section_repo: ISectionRepository | None = None,
        task_node_repo: ITaskNodeRepository | None = None,
    ) -> None:
        self._session = session
        self._repo = repo
        self._work_item_repo = work_item_repo
        self._section_repo = section_repo
        self._task_node_repo = task_node_repo

    async def create_version(
        self,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        trigger: VersionTrigger = VersionTrigger.CONTENT_EDIT,
        actor_type: VersionActorType = VersionActorType.HUMAN,
        commit_message: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> WorkItemVersion:
        """Write an append-only version row with SERIALIZABLE isolation.

        If snapshot is not provided, it is built from current DB state using
        the injected repositories (work_item_repo, section_repo, task_node_repo).

        Callers must not hold another transaction when invoking this — the
        SET TRANSACTION ISOLATION LEVEL statement must fire at the start of
        the DB transaction.
        """
        # Session may already be in SERIALIZABLE; continue silently.
        with contextlib.suppress(Exception):
            await self._session.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))

        if snapshot is None:
            snapshot = await self._build_snapshot(work_item_id, workspace_id)

        try:
            version = await self._repo.append(
                work_item_id,
                snapshot,
                actor_id,
                trigger=trigger.value,
                actor_type=actor_type.value,
                actor_id=actor_id,
                commit_message=commit_message,
            )
        except Exception as exc:  # IntegrityError / OperationalError
            raise VersionConflictError(
                f"could not create version for work_item_id={work_item_id}"
            ) from exc

        logger.info(
            "version created",
            extra={
                "work_item_id": str(work_item_id),
                "version_number": version.version_number,
                "trigger": trigger.value,
                "actor_type": actor_type.value,
            },
        )
        return version

    async def get_latest(self, work_item_id: UUID, workspace_id: UUID) -> WorkItemVersion | None:
        return await self._repo.get_latest(work_item_id, workspace_id)

    async def get_by_number(
        self, work_item_id: UUID, version_number: int, workspace_id: UUID
    ) -> WorkItemVersion | None:
        return await self._repo.get_by_number(work_item_id, version_number, workspace_id)

    async def list_for_work_item(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 20,
        before_version: int | None = None,
    ) -> list[WorkItemVersion]:
        return await self._repo.list_by_work_item(
            work_item_id,
            workspace_id,
            include_archived=include_archived,
            limit=limit,
            before_version=before_version,
        )

    async def _build_snapshot(self, work_item_id: UUID, workspace_id: UUID) -> dict[str, Any]:
        """Build v1 snapshot from current DB state."""
        snapshot: dict[str, Any] = {
            "schema_version": 1,
            "work_item": {},
            "sections": [],
            "task_node_ids": [],
        }

        if self._work_item_repo is not None:
            wi = await self._work_item_repo.get(work_item_id, workspace_id)
            if wi is not None:
                snapshot["work_item"] = {
                    "id": str(wi.id),
                    "title": wi.title,
                    "description": wi.description or "",
                    "state": wi.state.value if hasattr(wi.state, "value") else str(wi.state),
                    "owner_id": str(wi.owner_id) if wi.owner_id else None,
                }

        if self._section_repo is not None:
            sections = await self._section_repo.get_by_work_item(work_item_id)
            snapshot["sections"] = [
                {
                    "section_id": str(s.id),
                    "section_type": s.section_type.value
                    if hasattr(s.section_type, "value")
                    else str(s.section_type),
                    "content": s.content,
                    "order": s.display_order,
                }
                for s in sorted(sections, key=lambda s: s.display_order)
            ]

        if self._task_node_repo is not None:
            task_nodes = await self._task_node_repo.get_by_work_item(work_item_id)
            snapshot["task_node_ids"] = [str(tn.id) for tn in task_nodes]

        return snapshot
