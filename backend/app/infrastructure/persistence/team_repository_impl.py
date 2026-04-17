"""EP-08 — Team, TeamMembership, Notification repository implementations."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.team import Notification, Team, TeamMembership
from app.domain.queries.page import Page
from app.domain.repositories.team_repository import (
    INotificationRepository,
    ITeamMembershipRepository,
    ITeamRepository,
)
from app.infrastructure.persistence.mappers.team_mapper import (
    membership_to_domain,
    membership_to_orm,
    notification_to_domain,
    notification_to_orm,
    team_to_domain,
    team_to_orm,
)
from app.infrastructure.persistence.models.orm import (
    NotificationORM,
    TeamMembershipORM,
    TeamORM,
    UserORM,
)


class TeamRepositoryImpl(ITeamRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, team: Team) -> Team:
        self._session.add(team_to_orm(team))
        await self._session.flush()
        return team

    async def get(self, team_id: UUID) -> Team | None:
        row = await self._session.get(TeamORM, team_id)
        return team_to_domain(row) if row else None

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Team]:
        stmt = (
            select(TeamORM)
            .where(
                TeamORM.workspace_id == workspace_id,
                TeamORM.deleted_at.is_(None),
            )
            .order_by(TeamORM.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [team_to_domain(r) for r in rows]

    async def save(self, team: Team) -> Team:
        existing = await self._session.get(TeamORM, team.id)
        if existing is None:
            self._session.add(team_to_orm(team))
        else:
            existing.name = team.name
            existing.description = team.description
            existing.can_receive_reviews = team.can_receive_reviews
            existing.deleted_at = team.deleted_at
            existing.updated_at = team.updated_at
        await self._session.flush()
        return team


class TeamMembershipRepositoryImpl(ITeamMembershipRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_member(self, membership: TeamMembership) -> TeamMembership:
        self._session.add(membership_to_orm(membership))
        await self._session.flush()
        return membership

    async def get_active(self, team_id: UUID, user_id: UUID) -> TeamMembership | None:
        stmt = select(TeamMembershipORM).where(
            TeamMembershipORM.team_id == team_id,
            TeamMembershipORM.user_id == user_id,
            TeamMembershipORM.removed_at.is_(None),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return membership_to_domain(row) if row else None

    async def save(self, membership: TeamMembership) -> TeamMembership:
        existing = await self._session.get(TeamMembershipORM, membership.id)
        if existing is None:
            self._session.add(membership_to_orm(membership))
        else:
            existing.role = membership.role.value
            existing.removed_at = membership.removed_at
        await self._session.flush()
        return membership

    async def list_for_team(self, team_id: UUID) -> list[TeamMembership]:
        stmt = (
            select(TeamMembershipORM)
            .where(
                TeamMembershipORM.team_id == team_id,
                TeamMembershipORM.removed_at.is_(None),
            )
            .order_by(TeamMembershipORM.joined_at)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [membership_to_domain(r) for r in rows]

    async def list_teams_for_user(self, user_id: UUID, workspace_id: UUID) -> list[Team]:
        stmt = (
            select(TeamORM)
            .join(TeamMembershipORM, TeamMembershipORM.team_id == TeamORM.id)
            .where(
                TeamMembershipORM.user_id == user_id,
                TeamMembershipORM.removed_at.is_(None),
                TeamORM.workspace_id == workspace_id,
                TeamORM.deleted_at.is_(None),
            )
            .order_by(TeamORM.name)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [team_to_domain(r) for r in rows]

    async def list_active_members_with_users(
        self, team_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]:
        """Batch-load active memberships + user profile fields for N teams."""
        ids = list(team_ids)
        result: dict[UUID, list[dict[str, Any]]] = {tid: [] for tid in ids}
        if not ids:
            return result
        stmt = (
            select(TeamMembershipORM, UserORM)
            .join(UserORM, TeamMembershipORM.user_id == UserORM.id)
            .where(
                TeamMembershipORM.team_id.in_(ids),
                TeamMembershipORM.removed_at.is_(None),
            )
            .order_by(TeamMembershipORM.team_id, TeamMembershipORM.joined_at.asc())
        )
        rows = (await self._session.execute(stmt)).all()
        for membership, user in rows:
            result[membership.team_id].append(
                {
                    "id": str(membership.id),
                    "user_id": str(membership.user_id),
                    "full_name": user.full_name,
                    "email": user.email,
                    "avatar_url": user.avatar_url,
                    "role": membership.role,
                    "joined_at": membership.joined_at.isoformat(),
                }
            )
        return result


class NotificationRepositoryImpl(INotificationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, notification: Notification) -> Notification:
        # idempotent: return existing if key already seen
        existing = await self.get_by_idempotency_key(notification.idempotency_key)
        if existing is not None:
            return existing
        self._session.add(notification_to_orm(notification))
        await self._session.flush()
        return notification

    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> Notification | None:
        stmt = select(NotificationORM).where(
            NotificationORM.idempotency_key == idempotency_key
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return notification_to_domain(row) if row else None

    async def get(self, notification_id: UUID) -> Notification | None:
        row = await self._session.get(NotificationORM, notification_id)
        return notification_to_domain(row) if row else None

    async def list_unread_for_user(
        self,
        user_id: UUID,
        workspace_id: UUID,
        page: int,
        page_size: int,
    ) -> Page[Notification]:
        base = (
            select(NotificationORM)
            .where(
                NotificationORM.recipient_id == user_id,
                NotificationORM.workspace_id == workspace_id,
            )
            .order_by(
                # unread first, then by recency
                sa.case(
                    (NotificationORM.state == "unread", 0),
                    else_=1,
                ),
                NotificationORM.created_at.desc(),
            )
        )
        total_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self._session.execute(total_stmt)).scalar_one()
        rows = (
            await self._session.execute(
                base.offset((page - 1) * page_size).limit(page_size)
            )
        ).scalars().all()
        return Page(
            items=[notification_to_domain(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def save(self, notification: Notification) -> Notification:
        existing = await self._session.get(NotificationORM, notification.id)
        if existing is None:
            self._session.add(notification_to_orm(notification))
        else:
            existing.state = notification.state.value
            existing.read_at = notification.read_at
            existing.actioned_at = notification.actioned_at
        await self._session.flush()
        return notification
