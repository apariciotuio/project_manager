"""EP-08 — TeamService + NotificationService."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from app.domain.models.team import Notification, Team, TeamMembership, TeamRole
from app.domain.queries.page import Page
from app.domain.repositories.team_repository import (
    INotificationRepository,
    ITeamMembershipRepository,
    ITeamRepository,
)


class TeamNotFoundError(LookupError):
    pass


class TeamAlreadyDeletedError(ValueError):
    pass


class MembershipAlreadyExistsError(ValueError):
    pass


class MembershipNotFoundError(LookupError):
    pass


class NotificationNotFoundError(LookupError):
    pass


class TeamService:
    def __init__(
        self,
        *,
        team_repo: ITeamRepository,
        membership_repo: ITeamMembershipRepository,
    ) -> None:
        self._teams = team_repo
        self._memberships = membership_repo

    async def create(
        self,
        *,
        workspace_id: UUID,
        name: str,
        created_by: UUID,
        description: str | None = None,
        can_receive_reviews: bool = False,
    ) -> Team:
        team = Team.create(
            workspace_id=workspace_id,
            name=name,
            created_by=created_by,
            description=description,
            can_receive_reviews=can_receive_reviews,
        )
        return await self._teams.create(team)

    async def get(self, team_id: UUID, *, workspace_id: UUID) -> Team:
        """Return a team scoped to the caller's workspace.

        Raises TeamNotFoundError when the team does not exist OR belongs to
        another workspace — caller must not be able to distinguish the two
        cases (IDOR mitigation).
        """
        team = await self._teams.get(team_id)
        if team is None or team.workspace_id != workspace_id:
            raise TeamNotFoundError(f"team {team_id} not found")
        return team

    async def list_for_workspace(self, workspace_id: UUID) -> list[Team]:
        return await self._teams.list_active_for_workspace(workspace_id)

    async def list_members_for_teams(
        self, team_ids: Sequence[UUID]
    ) -> dict[UUID, list[dict[str, Any]]]:
        """Single-query batch fetch of active members (with user details) for N teams.

        Replaces the per-team resolve loop that produced an N+1 read pattern
        in the team-list endpoint.
        """
        return await self._memberships.list_active_members_with_users(team_ids)

    async def soft_delete(self, team_id: UUID) -> Team:
        team = await self._teams.get(team_id)
        if team is None:
            raise TeamNotFoundError(f"team {team_id} not found")
        if team.deleted_at is not None:
            raise TeamAlreadyDeletedError(f"team {team_id} already deleted")
        team.soft_delete()
        return await self._teams.save(team)

    async def add_member(
        self,
        *,
        team_id: UUID,
        user_id: UUID,
        role: TeamRole = TeamRole.MEMBER,
    ) -> TeamMembership:
        team = await self._teams.get(team_id)
        if team is None:
            raise TeamNotFoundError(f"team {team_id} not found")
        existing = await self._memberships.get_active(team_id, user_id)
        if existing is not None:
            raise MembershipAlreadyExistsError(
                f"user {user_id} is already a member of team {team_id}"
            )
        membership = TeamMembership.create(team_id=team_id, user_id=user_id, role=role)
        return await self._memberships.add_member(membership)

    async def remove_member(self, *, team_id: UUID, user_id: UUID) -> TeamMembership:
        membership = await self._memberships.get_active(team_id, user_id)
        if membership is None:
            raise MembershipNotFoundError(
                f"user {user_id} is not an active member of team {team_id}"
            )
        membership.remove()
        return await self._memberships.save(membership)

    async def list_members(self, team_id: UUID) -> list[TeamMembership]:
        return await self._memberships.list_for_team(team_id)


class NotificationService:
    def __init__(self, *, notification_repo: INotificationRepository) -> None:
        self._notifications = notification_repo

    async def enqueue(
        self,
        *,
        workspace_id: UUID,
        recipient_id: UUID,
        type: str,
        subject_type: str,
        subject_id: UUID,
        deeplink: str,
        idempotency_key: str,
        actor_id: UUID | None = None,
        quick_action: dict | None = None,
        extra: dict | None = None,
    ) -> Notification:
        notification = Notification.create(
            workspace_id=workspace_id,
            recipient_id=recipient_id,
            type=type,
            subject_type=subject_type,
            subject_id=subject_id,
            deeplink=deeplink,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            quick_action=quick_action,
            extra=extra,
        )
        return await self._notifications.create(notification)

    async def list_inbox(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Page[Notification]:
        return await self._notifications.list_unread_for_user(
            user_id, workspace_id, page, page_size
        )

    async def mark_read(self, notification_id: UUID) -> Notification:
        notification = await self._notifications.get(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"notification {notification_id} not found")
        notification.mark_read()
        return await self._notifications.save(notification)

    async def mark_actioned(self, notification_id: UUID) -> Notification:
        notification = await self._notifications.get(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"notification {notification_id} not found")
        notification.mark_actioned()
        return await self._notifications.save(notification)
