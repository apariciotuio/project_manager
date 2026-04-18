"""IAssistantSuggestionRepository — domain-layer interface for suggestion persistence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus


class IAssistantSuggestionRepository(ABC):
    @abstractmethod
    async def create_batch(
        self, suggestions: list[AssistantSuggestion]
    ) -> list[AssistantSuggestion]:
        """Bulk-insert suggestions. Returns persisted entities with server-assigned timestamps."""

    @abstractmethod
    async def get_by_id(self, suggestion_id: UUID) -> AssistantSuggestion | None:
        """Return suggestion by primary key or None."""

    @abstractmethod
    async def get_by_batch_id(self, batch_id: UUID) -> list[AssistantSuggestion]:
        """Return all suggestions belonging to a batch."""

    @abstractmethod
    async def get_by_dundun_request_id(self, dundun_request_id: str) -> list[AssistantSuggestion]:
        """Return suggestions tied to a specific Dundun async request."""

    @abstractmethod
    async def list_pending_for_work_item(self, work_item_id: UUID) -> list[AssistantSuggestion]:
        """Return non-expired pending suggestions for a work item.

        Excludes accepted, rejected, and expired rows.
        """

    @abstractmethod
    async def update_status(
        self,
        ids: list[UUID],
        status: SuggestionStatus,
        now: datetime,
    ) -> int:
        """Single-query bulk status update. Returns number of rows affected.

        Returns 0 when ``ids`` is empty.
        """
