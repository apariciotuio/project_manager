"""AuditService — fire-and-forget wrapper around IAuditRepository.

Fire-and-forget contract: `log_event` MUST NOT raise, even if the repo fails. An
exception in audit logging must never block the user-facing auth flow.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

from app.domain.models.audit_event import AuditCategory, AuditEvent
from app.domain.repositories.audit_repository import IAuditRepository

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, audit_repo: IAuditRepository) -> None:
        self._repo = audit_repo

    async def log_event(
        self,
        *,
        category: AuditCategory,
        action: str,
        actor_id: UUID | None = None,
        actor_display: str | None = None,
        workspace_id: UUID | None = None,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        before_value: dict[str, Any] | None = None,
        after_value: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        event = AuditEvent(
            id=uuid4(),
            category=category,
            action=action,
            actor_id=actor_id,
            actor_display=actor_display,
            workspace_id=workspace_id,
            entity_type=entity_type,
            entity_id=entity_id,
            before_value=before_value,
            after_value=after_value,
            context=context or {},
        )
        try:
            await self._repo.append(event)
        except Exception:
            logger.exception(
                "audit log failed (category=%s action=%s actor=%s)",
                category,
                action,
                actor_id,
            )
