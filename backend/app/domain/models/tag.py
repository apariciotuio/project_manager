"""EP-15 — Tag and WorkItemTag domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4


class TagNotFoundError(Exception):
    pass


class TagArchivedError(Exception):
    pass


@dataclass
class Tag:
    id: UUID
    workspace_id: UUID
    name: str
    color: str | None
    archived_at: datetime | None
    created_at: datetime
    created_by: UUID

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    def archive(self) -> None:
        if self.archived_at is not None:
            return
        self.archived_at = datetime.now(UTC)

    def rename(self, name: str) -> None:
        if not name.strip():
            raise ValueError("Tag name cannot be empty")
        if self.archived_at is not None:
            raise TagArchivedError("Cannot rename an archived tag")
        self.name = name.strip()

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        color: str | None = None,
    ) -> Tag:
        if not name.strip():
            raise ValueError("Tag name cannot be empty")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip(),
            color=color,
            archived_at=None,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )


@dataclass
class WorkItemTag:
    id: UUID
    work_item_id: UUID
    tag_id: UUID
    created_at: datetime
    created_by: UUID

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        tag_id: UUID,
        created_by: UUID,
    ) -> WorkItemTag:
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            tag_id=tag_id,
            created_at=datetime.now(UTC),
            created_by=created_by,
        )
