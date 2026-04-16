"""AuditEvent — immutable record of a single audited action.

EP-00 auth + EP-10 admin/domain events share this single entity (category column).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

AuditCategory = Literal["auth", "admin", "domain"]


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class AuditEvent:
    id: UUID
    category: AuditCategory
    action: str
    actor_id: UUID | None = None
    actor_display: str | None = None
    workspace_id: UUID | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    before_value: dict[str, Any] | None = None
    after_value: dict[str, Any] | None = None
    context: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    @classmethod
    def auth(
        cls,
        *,
        action: str,
        actor_id: UUID | None = None,
        actor_display: str | None = None,
        workspace_id: UUID | None = None,
        context: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            id=uuid4(),
            category="auth",
            action=action,
            actor_id=actor_id,
            actor_display=actor_display,
            workspace_id=workspace_id,
            context=context or {},
        )
