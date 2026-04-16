"""Template domain entity — pure, no infrastructure dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.value_objects.work_item_type import WorkItemType

_MAX_CONTENT_LENGTH = 50000


@dataclass
class Template:
    id: UUID
    workspace_id: UUID | None  # None = system default
    type: WorkItemType
    name: str
    content: str
    is_system: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if self.is_system and self.workspace_id is not None:
            raise ValueError(
                "system template must not have a workspace_id; "
                "set workspace_id=None for system templates"
            )
        if len(self.content) > _MAX_CONTENT_LENGTH:
            raise ValueError(
                f"content exceeds maximum length of {_MAX_CONTENT_LENGTH} characters; "
                f"got {len(self.content)}"
            )
