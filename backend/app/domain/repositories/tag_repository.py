"""EP-15 — Tag + WorkItemTag repository interfaces."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.tag import Tag, WorkItemTag


class ITagRepository(Protocol):
    async def create(self, tag: Tag) -> Tag: ...

    async def get(self, tag_id: UUID) -> Tag | None: ...

    async def save(self, tag: Tag) -> Tag: ...

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Tag]: ...

    async def search_by_prefix(self, workspace_id: UUID, prefix: str) -> list[Tag]: ...


class IWorkItemTagRepository(Protocol):
    async def add_tag(self, work_item_tag: WorkItemTag) -> WorkItemTag: ...

    async def remove_tag(self, work_item_id: UUID, tag_id: UUID) -> None: ...

    async def list_for_work_item(self, work_item_id: UUID) -> list[WorkItemTag]: ...
