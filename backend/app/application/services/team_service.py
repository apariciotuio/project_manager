"""EP-08 — TeamService + NotificationService."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any
from uuid import UUID

from app.domain.models.team import Notification, NotificationState, Team, TeamMembership, TeamRole
from app.domain.queries.page import Page
from app.domain.repositories.team_repository import (
    INotificationRepository,
    ITeamMembershipRepository,
    ITeamRepository,
)
from app.infrastructure.pagination import PaginationCursor, PaginationResult


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


class StaleActionError(ValueError):
    """Raised when execute_action is called on an already-actioned notification."""


class LastLeadError(ValueError):
    """Raised when the last lead of a team would be removed or demoted."""


class TeamHasOpenReviewsError(ValueError):
    """Raised when a team with open pending reviews is deleted."""


class TeamService:
    def __init__(
        self,
        *,
        team_repo: ITeamRepository,
        membership_repo: ITeamMembershipRepository,
        review_repo: object | None = None,
        is_user_suspended: Callable[[UUID], bool] | None = None,
    ) -> None:
        self._teams = team_repo
        self._memberships = membership_repo
        self._review_repo = review_repo
        self._is_user_suspended = is_user_suspended or (lambda _: False)

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
        created = await self._teams.create(team)
        # Auto-add creator as lead (spec: US-080)
        membership = TeamMembership.create(
            team_id=created.id,
            user_id=created_by,
            role=TeamRole.LEAD,
        )
        await self._memberships.add_member(membership)
        return created

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
        if self._review_repo is not None:
            has_open = await self._review_repo.has_open_reviews_for_team(team_id)
            if has_open:
                raise TeamHasOpenReviewsError(
                    f"team {team_id} has open pending reviews and cannot be deleted"
                )
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
        if self._is_user_suspended(user_id):
            raise ValueError(f"user {user_id} is suspended and cannot receive team assignments")
        existing_active = await self._memberships.get_active(team_id, user_id)
        if existing_active is not None:
            # Idempotent: already active member, no-op
            return existing_active
        # Re-activation: check for a removed membership to reuse
        if hasattr(self._memberships, "get_any"):
            any_membership = await self._memberships.get_any(team_id, user_id)
            if any_membership is not None and any_membership.removed_at is not None:
                any_membership.removed_at = None
                return await self._memberships.save(any_membership)
        membership = TeamMembership.create(team_id=team_id, user_id=user_id, role=role)
        return await self._memberships.add_member(membership)

    async def remove_member(self, *, team_id: UUID, user_id: UUID) -> TeamMembership:
        membership = await self._memberships.get_active(team_id, user_id)
        if membership is None:
            raise MembershipNotFoundError(
                f"user {user_id} is not an active member of team {team_id}"
            )
        if membership.role == TeamRole.LEAD:
            lead_count = await self._memberships.count_active_leads(team_id)
            if lead_count <= 1:
                raise LastLeadError(f"cannot remove the last lead from team {team_id}")
        membership.remove()
        return await self._memberships.save(membership)

    async def update_role(
        self,
        *,
        team_id: UUID,
        user_id: UUID,
        new_role: TeamRole,
    ) -> TeamMembership:
        membership = await self._memberships.get_active(team_id, user_id)
        if membership is None:
            raise MembershipNotFoundError(
                f"user {user_id} is not an active member of team {team_id}"
            )
        # Guard: demoting a lead when they are the last one
        if membership.role == TeamRole.LEAD and new_role != TeamRole.LEAD:
            lead_count = await self._memberships.count_active_leads(team_id)
            if lead_count <= 1:
                raise LastLeadError(f"cannot demote the last lead of team {team_id}")
        membership.role = new_role
        return await self._memberships.save(membership)

    async def list_members(self, team_id: UUID) -> list[TeamMembership]:
        return await self._memberships.list_for_team(team_id)


class NotificationService:
    def __init__(
        self,
        *,
        notification_repo: INotificationRepository,
        quick_action_dispatcher: object | None = None,
    ) -> None:
        self._notifications = notification_repo
        self._dispatcher = quick_action_dispatcher

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

    async def list_inbox_cursor(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        cursor: PaginationCursor | None,
        page_size: int,
    ) -> PaginationResult:
        return await self._notifications.list_inbox_cursor(
            user_id,
            workspace_id,
            cursor=cursor,
            page_size=page_size,
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

    async def execute_action(
        self,
        *,
        notification_id: UUID,
        actor_id: UUID,
    ) -> dict:
        """Execute a quick action from the inbox.

        Raises:
            NotificationNotFoundError: notification not found.
            StaleActionError: notification is already actioned.
        """

        notification = await self._notifications.get(notification_id)
        if notification is None:
            raise NotificationNotFoundError(f"notification {notification_id} not found")

        if notification.state == NotificationState.ACTIONED:
            raise StaleActionError(f"notification {notification_id} is already actioned")

        quick_action = notification.quick_action
        if quick_action is None or "action" not in quick_action:
            raise ValueError(f"notification {notification_id} has no quick_action")

        action_type = quick_action["action"]
        action_result: dict[str, Any] = {}

        if self._dispatcher is not None:
            action_result = await self._dispatcher.dispatch(
                action_type=action_type,
                subject_id=notification.subject_id,
                actor_id=actor_id,
            )

        notification.mark_actioned()
        saved = await self._notifications.save(notification)

        return {
            "result": action_result,
            "notification": {
                "id": str(saved.id),
                "state": saved.state.value,
                "actioned_at": saved.actioned_at.isoformat() if saved.actioned_at else None,
            },
        }
