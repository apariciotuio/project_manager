"""EP-04/EP-07 — IWorkItemVersionRepository (append-only).

EP-07's VersioningService is the sole writer. Other services must go through
VersioningService.create_version().

workspace_id is required on all reads to prevent cross-workspace data leaks.
Returns None (not 403) on workspace mismatch to avoid existence disclosure.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.domain.models.work_item_version import WorkItemVersion


class IWorkItemVersionRepository(ABC):
    @abstractmethod
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
    ) -> WorkItemVersion: ...

    @abstractmethod
    async def get_latest(self, work_item_id: UUID, workspace_id: UUID) -> WorkItemVersion | None: ...

    @abstractmethod
    async def get(self, version_id: UUID, workspace_id: UUID) -> WorkItemVersion | None: ...

    @abstractmethod
    async def get_by_number(
        self, work_item_id: UUID, version_number: int, workspace_id: UUID
    ) -> WorkItemVersion | None: ...

    @abstractmethod
    async def list_by_work_item(
        self,
        work_item_id: UUID,
        workspace_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 20,
        before_version: int | None = None,
    ) -> list[WorkItemVersion]: ...
