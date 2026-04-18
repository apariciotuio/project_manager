"""Repository interface for Invitation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.invitation import Invitation


class IInvitationRepository(ABC):
    @abstractmethod
    async def create(self, invitation: Invitation) -> Invitation: ...

    @abstractmethod
    async def get_by_id(self, invitation_id: UUID) -> Invitation | None: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> Invitation | None: ...

    @abstractmethod
    async def get_active_by_email(self, workspace_id: UUID, email: str) -> Invitation | None:
        """Return the most recent non-expired, non-revoked invitation for this email."""
        ...

    @abstractmethod
    async def save(self, invitation: Invitation) -> Invitation: ...

    @abstractmethod
    async def list_for_workspace(
        self, workspace_id: UUID, *, state: str | None = None
    ) -> list[Invitation]: ...
