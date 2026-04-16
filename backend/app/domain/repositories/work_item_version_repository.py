"""EP-04 — IWorkItemVersionRepository (append-only).

EP-07's VersioningService is the sole writer. Other services must go through
VersioningService.create_version().
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
    ) -> WorkItemVersion: ...

    @abstractmethod
    async def get_latest(self, work_item_id: UUID) -> WorkItemVersion | None: ...

    @abstractmethod
    async def get(self, version_id: UUID) -> WorkItemVersion | None: ...
