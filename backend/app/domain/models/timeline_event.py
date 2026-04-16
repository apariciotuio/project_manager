"""EP-07 — TimelineEvent value object.

Append-only audit row written via the outbox pattern from domain service
hooks. workspace_id is denormalised for fast workspace-scoped queries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class TimelineActorType(StrEnum):
    HUMAN = "human"
    AI_SUGGESTION = "ai_suggestion"
    SYSTEM = "system"


@dataclass(frozen=True)
class TimelineEvent:
    id: UUID
    work_item_id: UUID
    workspace_id: UUID
    event_type: str
    actor_type: TimelineActorType
    actor_id: UUID | None
    actor_display_name: str | None
    summary: str
    payload: dict[str, Any]
    occurred_at: datetime
    source_id: UUID | None
    source_table: str | None

    @classmethod
    def create(
        cls,
        *,
        work_item_id: UUID,
        workspace_id: UUID,
        event_type: str,
        actor_type: TimelineActorType,
        summary: str,
        actor_id: UUID | None = None,
        actor_display_name: str | None = None,
        payload: dict[str, Any] | None = None,
        source_id: UUID | None = None,
        source_table: str | None = None,
    ) -> TimelineEvent:
        if len(summary) > 255:
            raise ValueError("summary exceeds 255 characters")
        return cls(
            id=uuid4(),
            work_item_id=work_item_id,
            workspace_id=workspace_id,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            summary=summary,
            payload=payload or {},
            occurred_at=datetime.now(UTC),
            source_id=source_id,
            source_table=source_table,
        )
