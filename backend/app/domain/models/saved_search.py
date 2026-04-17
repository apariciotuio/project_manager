"""EP-09 — SavedSearch entity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class SavedSearch:
    id: UUID
    user_id: UUID
    workspace_id: UUID
    name: str
    query_params: dict[str, Any]
    is_shared: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        workspace_id: UUID,
        name: str,
        query_params: dict[str, Any] | None = None,
        is_shared: bool = False,
    ) -> SavedSearch:
        if not name.strip():
            raise ValueError("saved search name cannot be empty")
        if len(name) > 255:
            raise ValueError("saved search name exceeds 255 characters")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            workspace_id=workspace_id,
            name=name.strip(),
            query_params=query_params or {},
            is_shared=is_shared,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str | None = None,
        query_params: dict[str, Any] | None = None,
        is_shared: bool | None = None,
    ) -> None:
        if name is not None:
            if not name.strip():
                raise ValueError("saved search name cannot be empty")
            if len(name) > 255:
                raise ValueError("saved search name exceeds 255 characters")
            self.name = name.strip()
        if query_params is not None:
            self.query_params = query_params
        if is_shared is not None:
            self.is_shared = is_shared
        self.updated_at = datetime.now(UTC)
