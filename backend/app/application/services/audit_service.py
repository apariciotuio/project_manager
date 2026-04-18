"""AuditService — fire-and-forget wrapper around IAuditRepository.

Fire-and-forget contract: `log_event` MUST NOT raise, even if the repo fails. An
exception in audit logging must never block the user-facing auth flow.

Session isolation (session_factory mode): when constructed with a session_factory,
`log_event()` opens, writes, commits, and closes an independent session per call.
This guarantees audit rows survive even when the surrounding request transaction
is rolled back — e.g. failure audit for an invalid FSM transition.

Legacy mode: when constructed with an IAuditRepository directly, delegates to it
as before (session lifecycle is the caller's responsibility).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

from app.domain.models.audit_event import AuditCategory, AuditEvent
from app.domain.repositories.audit_repository import IAuditRepository

logger = logging.getLogger(__name__)

# Type alias for the session factory callable produced by async_sessionmaker.
_SessionFactory = Callable[[], Any]


class AuditService:
    """Audit logger with two construction modes.

    AuditService(audit_repo)          — legacy; repo owns session, caller commits.
    AuditService.isolated(factory)    — each log_event() opens its own session and
                                        commits independently.
    """

    def __init__(self, audit_repo: IAuditRepository) -> None:
        self._repo: IAuditRepository | None = audit_repo
        self._factory: _SessionFactory | None = None

    @classmethod
    def isolated(cls, session_factory: _SessionFactory) -> "AuditService":
        """Build an AuditService that commits each audit write in its own session.

        Use this when the surrounding request session may be rolled back (e.g.
        the work-item transition failure path).
        """
        instance = cls.__new__(cls)
        instance._repo = None
        instance._factory = session_factory
        return instance

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
            if self._factory is not None:
                # Isolated mode: own session, own commit, independent of caller tx.
                # Deferred import to avoid circular imports at module load time.
                from app.infrastructure.persistence.audit_repository_impl import (
                    AuditRepositoryImpl,
                )

                async with self._factory() as session:
                    repo = AuditRepositoryImpl(session)
                    await repo.append(event)
                    await session.commit()
            else:
                assert self._repo is not None  # invariant: one of the two is set
                await self._repo.append(event)
        except Exception:
            logger.exception(
                "audit log failed (category=%s action=%s actor=%s)",
                category,
                action,
                actor_id,
            )
