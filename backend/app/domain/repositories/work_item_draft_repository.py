"""IWorkItemDraftRepository — domain-layer interface for pre-creation draft persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.value_objects.draft_conflict import DraftConflict


class IWorkItemDraftRepository(ABC):
    @abstractmethod
    async def upsert(
        self, draft: WorkItemDraft, expected_version: int
    ) -> WorkItemDraft | DraftConflict:
        """Insert or update draft with optimistic version check.

        If the server's current local_version > expected_version, returns DraftConflict
        with server state. Otherwise, increments local_version and persists.
        New drafts (no existing row) are always inserted (expected_version is treated as 0).
        """

    @abstractmethod
    async def get_by_user_workspace(
        self, user_id: UUID, workspace_id: UUID
    ) -> WorkItemDraft | None:
        """Return current draft for user+workspace or None."""

    @abstractmethod
    async def delete(self, draft_id: UUID, user_id: UUID) -> None:
        """Delete draft. Raises DraftForbiddenError if user_id doesn't own it.
        Raises WorkItemDraftNotFoundError if draft doesn't exist.
        """

    @abstractmethod
    async def get_expired(self) -> list[WorkItemDraft]:
        """Return all drafts where expires_at < now(). Used by cleanup job."""

    @abstractmethod
    async def delete_expired(self) -> int:
        """Delete all expired drafts in a single query. Returns count deleted."""
