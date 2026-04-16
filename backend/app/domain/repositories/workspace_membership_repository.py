"""Abstract interface for WorkspaceMembership persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.workspace_membership import WorkspaceMembership


class IWorkspaceMembershipRepository(ABC):
    @abstractmethod
    async def create(self, membership: WorkspaceMembership) -> WorkspaceMembership: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        """Return all memberships for a user across workspaces (any state)."""
        ...

    @abstractmethod
    async def get_active_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        """Return only `state == 'active'` memberships. Used by OAuth callback routing."""
        ...

    @abstractmethod
    async def get_default_for_user(self, user_id: UUID) -> WorkspaceMembership | None: ...
