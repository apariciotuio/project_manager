"""WorkItemDraft domain entity — pre-creation draft, pure, no infra dependencies."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


def _default_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=30)


@dataclass
class WorkItemDraft:
    id: UUID
    user_id: UUID
    workspace_id: UUID
    data: dict  # type: ignore[type-arg]
    local_version: int
    incomplete: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        workspace_id: UUID,
        data: dict,  # type: ignore[type-arg]
        incomplete: bool = True,
    ) -> WorkItemDraft:
        now = _now()
        return cls(
            id=uuid4(),
            user_id=user_id,
            workspace_id=workspace_id,
            data=data,
            local_version=1,
            incomplete=incomplete,
            created_at=now,
            updated_at=now,
            expires_at=_default_expiry(),
        )
