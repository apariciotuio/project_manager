"""EP-08 — ITeamRepository, ITeamMembershipRepository, INotificationRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.team import Notification, Team, TeamMembership
from app.domain.queries.page import Page


class ITeamRepository(ABC):
    @abstractmethod
    async def create(self, team: Team) -> Team: ...

    @abstractmethod
    async def get(self, team_id: UUID) -> Team | None: ...

    @abstractmethod
    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Team]: ...

    @abstractmethod
    async def save(self, team: Team) -> Team: ...


class ITeamMembershipRepository(ABC):
    @abstractmethod
    async def add_member(self, membership: TeamMembership) -> TeamMembership: ...

    @abstractmethod
    async def get_active(self, team_id: UUID, user_id: UUID) -> TeamMembership | None: ...

    @abstractmethod
    async def save(self, membership: TeamMembership) -> TeamMembership: ...

    @abstractmethod
    async def list_for_team(self, team_id: UUID) -> list[TeamMembership]: ...

    @abstractmethod
    async def list_teams_for_user(self, user_id: UUID, workspace_id: UUID) -> list[Team]: ...


class INotificationRepository(ABC):
    @abstractmethod
    async def create(self, notification: Notification) -> Notification: ...

    @abstractmethod
    async def get_by_idempotency_key(
        self, idempotency_key: str
    ) -> Notification | None: ...

    @abstractmethod
    async def get(self, notification_id: UUID) -> Notification | None: ...

    @abstractmethod
    async def list_unread_for_user(
        self,
        user_id: UUID,
        workspace_id: UUID,
        page: int,
        page_size: int,
    ) -> Page[Notification]: ...

    @abstractmethod
    async def save(self, notification: Notification) -> Notification: ...
