"""EP-07 — WorkItemVersion (append-only, full snapshot).

EP-07's VersioningService is the sole writer to work_item_versions. Other
services call VersioningService.create_version(...) instead of inserting here
directly.

Trigger enum: content_edit | state_transition | review_outcome | breakdown_change | manual
ActorType enum: human | ai_suggestion | system
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class VersionTrigger(StrEnum):
    CONTENT_EDIT = "content_edit"
    STATE_TRANSITION = "state_transition"
    REVIEW_OUTCOME = "review_outcome"
    BREAKDOWN_CHANGE = "breakdown_change"
    MANUAL = "manual"
    AI_SUGGESTION = "ai_suggestion"


class VersionActorType(StrEnum):
    HUMAN = "human"
    AI_SUGGESTION = "ai_suggestion"
    SYSTEM = "system"


@dataclass(frozen=True)
class WorkItemVersion:
    id: UUID
    work_item_id: UUID
    version_number: int
    snapshot: dict[str, Any]
    created_by: UUID
    created_at: datetime
    # EP-07 extended columns
    snapshot_schema_version: int = 1
    trigger: VersionTrigger = VersionTrigger.CONTENT_EDIT
    actor_type: VersionActorType = VersionActorType.HUMAN
    actor_id: UUID | None = None
    commit_message: str | None = None
    archived: bool = False
    workspace_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.version_number <= 0:
            raise ValueError(f"version_number must be positive, got {self.version_number}")
        # trigger validation (StrEnum already enforces on construction, but
        # protect against raw string construction via dataclass)
        if not isinstance(self.trigger, VersionTrigger):
            # will raise ValueError if invalid
            object.__setattr__(self, "trigger", VersionTrigger(self.trigger))
        if not isinstance(self.actor_type, VersionActorType):
            object.__setattr__(self, "actor_type", VersionActorType(self.actor_type))
