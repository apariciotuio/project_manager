"""Abstract interface for audit event persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.audit_event import AuditEvent
from app.infrastructure.pagination import PaginationCursor, PaginationResult


class IAuditRepository(ABC):
    @abstractmethod
    async def append(self, event: AuditEvent) -> AuditEvent:
        """Persist the event and return the persisted entity.

        Append-only: no update() or delete() methods exist on this interface.
        May raise on DB failure — callers wrap with fire-and-forget.
        """
        ...

    @abstractmethod
    async def list_cursor(
        self,
        workspace_id: UUID,
        *,
        cursor: PaginationCursor | None,
        page_size: int,
        category: str | None = None,
        action: str | None = None,
    ) -> PaginationResult:
        """Keyset-paginated list of audit events for a workspace.

        Ordered by (created_at DESC, id DESC).
        """
        ...
