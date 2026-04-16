"""EP-08 — NotificationRepositoryImpl."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.team import Notification
from app.domain.repositories.notification_repository import INotificationRepository
from app.infrastructure.persistence.mappers.notification_mapper import (
    notification_to_domain,
    notification_to_orm,
)
from app.infrastructure.persistence.models.orm import NotificationORM


class NotificationRepositoryImpl(INotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, notification: Notification) -> Notification:
        row = notification_to_orm(notification)
        self._session.add(row)
        await self._session.flush()
        return notification_to_domain(row)

    async def get(self, notification_id: UUID) -> Notification | None:
        row = await self._session.get(NotificationORM, notification_id)
        return notification_to_domain(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        stmt = (
            select(NotificationORM)
            .where(NotificationORM.recipient_id == user_id)
            .order_by(NotificationORM.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [notification_to_domain(r) for r in rows]

    async def mark_read(self, notification_id: UUID) -> None:
        await self._session.execute(
            update(NotificationORM)
            .where(
                NotificationORM.id == notification_id,
                NotificationORM.state == "unread",
            )
            .values(state="read", read_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def mark_actioned(self, notification_id: UUID) -> None:
        await self._session.execute(
            update(NotificationORM)
            .where(NotificationORM.id == notification_id)
            .values(state="actioned", actioned_at=datetime.now(UTC))
        )
        await self._session.flush()
