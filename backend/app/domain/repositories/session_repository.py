"""Abstract interface for Session persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.session import Session


class ISessionRepository(ABC):
    @abstractmethod
    async def create(self, session: Session) -> Session: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> Session | None: ...

    @abstractmethod
    async def revoke(self, session_id: UUID) -> None: ...

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete rows where `expires_at < now()`; return count removed."""
        ...
