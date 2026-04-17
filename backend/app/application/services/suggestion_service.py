"""SuggestionService — suggestion lifecycle (generate + status management) — EP-03.

# TODO: EP-04+EP-07 — implement apply_partial when sections/versioning land
#   apply_partial(batch_id, accepted_suggestion_ids) requires:
#     - work_item_sections table (EP-04)
#     - VersioningService.create_version (EP-07)
#     - SELECT FOR UPDATE on work_item row to serialize concurrent applies (TC-1)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.domain.ports.dundun import DundunClient
from app.domain.repositories.assistant_suggestion_repository import (
    IAssistantSuggestionRepository,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SuggestionService:
    def __init__(
        self,
        *,
        suggestion_repo: IAssistantSuggestionRepository,
        dundun_client: DundunClient,
        callback_url: str,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._dundun_client = dundun_client
        self._callback_url = callback_url
        self._now = now

    async def generate(
        self,
        work_item_id: UUID,
        user_id: UUID,
        thread_id: UUID | None = None,  # noqa: ARG002 — reserved for Phase 3b callback wiring
    ) -> UUID:
        """Dispatch Dundun wm_suggestion_agent asynchronously. Returns batch_id.

        No suggestion rows are created here — rows are created when Dundun POSTs
        to the callback controller (Phase 3b). The batch_id is what the callback
        will reference.
        """
        batch_id = uuid4()

        result = await self._dundun_client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=user_id,
            conversation_id=None,
            work_item_id=work_item_id,
            callback_url=self._callback_url,
            payload={"batch_id": str(batch_id)},
        )
        request_id = result["request_id"]
        logger.info(
            "suggestion_generation_dispatched work_item=%s batch_id=%s request_id=%s",
            work_item_id,
            batch_id,
            request_id,
        )
        return batch_id

    async def list_pending_for_work_item(
        self, work_item_id: UUID
    ) -> list[AssistantSuggestion]:
        """Return non-expired pending suggestions for a work item."""
        return await self._suggestion_repo.list_pending_for_work_item(work_item_id)

    async def list_for_batch(self, batch_id: UUID) -> list[AssistantSuggestion]:
        """Return every suggestion item in the batch (controller-facing passthrough)."""
        return await self._suggestion_repo.get_by_batch_id(batch_id)

    async def update_single_status(
        self, item_id: UUID, new_status: SuggestionStatus
    ) -> AssistantSuggestion:
        """Accept or reject a single suggestion by id."""
        suggestion = await self._suggestion_repo.get_by_id(item_id)
        if suggestion is None:
            raise ValueError(f"Suggestion {item_id} not found")

        now = self._now()
        if new_status == SuggestionStatus.ACCEPTED:
            updated = suggestion.accept(now)
        elif new_status == SuggestionStatus.REJECTED:
            updated = suggestion.reject(now)
        else:
            raise ValueError(f"Cannot transition to status {new_status!r} via update_single_status")

        await self._suggestion_repo.update_status([item_id], new_status, now)
        logger.info(
            "suggestion_status_updated id=%s status=%s", item_id, new_status.value
        )
        return updated
