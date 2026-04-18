"""EP-10 — Project, RoutingRule domain entities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class Project:
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        description: str | None = None,
    ) -> Project:
        if not name.strip():
            raise ValueError("project name cannot be empty")
        if len(name) > 255:
            raise ValueError("project name exceeds 255 characters")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip(),
            description=description,
            deleted_at=None,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)


@dataclass
class RoutingRule:
    id: UUID
    workspace_id: UUID
    project_id: UUID | None
    work_item_type: str
    suggested_team_id: UUID | None
    suggested_owner_id: UUID | None
    suggested_validators: list[Any]
    priority: int
    active: bool
    created_at: datetime
    updated_at: datetime
    created_by: UUID

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        work_item_type: str,
        created_by: UUID,
        project_id: UUID | None = None,
        suggested_team_id: UUID | None = None,
        suggested_owner_id: UUID | None = None,
        suggested_validators: list[Any] | None = None,
        priority: int = 0,
        active: bool = True,
    ) -> RoutingRule:
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            project_id=project_id,
            work_item_type=work_item_type,
            suggested_team_id=suggested_team_id,
            suggested_owner_id=suggested_owner_id,
            suggested_validators=suggested_validators or [],
            priority=priority,
            active=active,
            created_at=now,
            updated_at=now,
            created_by=created_by,
        )

    def deactivate(self) -> None:
        self.active = False
        self.updated_at = datetime.now(UTC)
