"""ContextPreset domain entity — EP-10 admin context presets."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class ContextSource:
    """Single source entry within a preset (stored as JSONB array)."""

    label: str
    url: str
    description: str | None = None
    source_type: str = "url"  # url | text | file

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "url": self.url,
            "description": self.description,
            "source_type": self.source_type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSource:
        return cls(
            label=data["label"],
            url=data["url"],
            description=data.get("description"),
            source_type=data.get("source_type", "url"),
        )


@dataclass
class ContextPreset:
    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    sources: list[ContextSource]
    deleted_at: datetime | None
    created_by: UUID
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    @classmethod
    def create(
        cls,
        *,
        workspace_id: UUID,
        name: str,
        description: str | None,
        sources: list[ContextSource],
        created_by: UUID,
    ) -> ContextPreset:
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if len(name) > 200:
            raise ValueError("name too long (max 200 chars)")
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            name=name.strip(),
            description=description,
            sources=list(sources),
            deleted_at=None,
            created_by=created_by,
        )

    def update(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        sources: list[ContextSource] | None = None,
    ) -> None:
        if name is not None:
            if not name.strip():
                raise ValueError("name must not be empty")
            if len(name) > 200:
                raise ValueError("name too long (max 200 chars)")
            self.name = name.strip()
        if description is not None:
            self.description = description
        if sources is not None:
            self.sources = list(sources)
        self.updated_at = _now()

    def soft_delete(self) -> None:
        if self.deleted_at is not None:
            return
        self.deleted_at = _now()

    def is_deleted(self) -> bool:
        return self.deleted_at is not None
