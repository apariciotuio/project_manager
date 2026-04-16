"""SQLAlchemy implementation of IAuditRepository."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.audit_event import AuditEvent
from app.domain.repositories.audit_repository import IAuditRepository
from app.infrastructure.persistence.models.orm import AuditEventORM


class AuditRepositoryImpl(IAuditRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: AuditEvent) -> None:
        row = AuditEventORM(
            id=event.id,
            category=event.category,
            action=event.action,
            actor_id=event.actor_id,
            actor_display=event.actor_display,
            workspace_id=event.workspace_id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            before_value=event.before_value,
            after_value=event.after_value,
            context=event.context,
            created_at=event.created_at,
        )
        self._session.add(row)
        await self._session.flush()
