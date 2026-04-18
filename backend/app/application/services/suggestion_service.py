"""SuggestionService — suggestion lifecycle (generate + status management) — EP-03.

Phase 3.7: apply_accepted_batch writes accepted suggestions to sections and
triggers versioning. Requires SectionService + VersioningService injected.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.domain.models.work_item_version import VersionActorType, VersionTrigger, WorkItemVersion
from app.domain.ports.dundun import DundunClient
from app.domain.repositories.assistant_suggestion_repository import (
    IAssistantSuggestionRepository,
)

if TYPE_CHECKING:
    from app.application.services.section_service import SectionService
    from app.application.services.versioning_service import VersioningService

logger = logging.getLogger(__name__)


class VersionConflictError(Exception):
    """Raised when applying a suggestion batch against a stale version target.

    The batch carries ``version_number_target`` — the WorkItemVersion the
    suggestions were generated against. If the work item has advanced past
    that version (another editor landed a change, a concurrent apply won, a
    manual edit committed), applying the batch would silently overwrite the
    newer content. Caller must either regenerate suggestions against the
    current version or merge manually.
    """


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
        section_service: "SectionService | None" = None,
        versioning_service: "VersioningService | None" = None,
        workspace_id: UUID | None = None,
    ) -> None:
        self._suggestion_repo = suggestion_repo
        self._dundun_client = dundun_client
        self._callback_url = callback_url
        self._now = now
        self._section_service = section_service
        self._versioning_service = versioning_service
        self._workspace_id = workspace_id

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

    async def apply_accepted_batch(
        self,
        batch_id: UUID,
        actor_id: UUID,
    ) -> dict[str, Any]:
        """Apply all accepted suggestions in the batch to their target sections.

        For each accepted suggestion (status=accepted, section_id set):
          - calls SectionService.update_section with proposed_content
          - marks suggestion status as applied

        Idempotent: already-applied suggestions are counted as skipped.

        Returns:
          applied_count: number of suggestions successfully applied
          skipped_count: number skipped (pending/rejected/expired/applied/no section_id)
          latest_version: the most recently created WorkItemVersion for the work item,
                          or None if VersioningService is not injected

        Raises:
          LookupError: batch_id not found
          ValueError: batch found but contains no accepted suggestions to apply
        """
        suggestions = await self._suggestion_repo.get_by_batch_id(batch_id)
        if not suggestions:
            raise LookupError(f"Suggestion batch {batch_id} not found")

        now = self._now()
        # Suggestions eligible for this apply pass: accepted + have a section_id
        to_apply = [
            s for s in suggestions
            if s.status == SuggestionStatus.ACCEPTED and s.section_id is not None
        ]
        # Already applied are skipped (idempotency) but don't trigger the "nothing to do" error
        already_applied = [s for s in suggestions if s.status == SuggestionStatus.APPLIED]
        skipped = len(suggestions) - len(to_apply)

        if not to_apply and not already_applied:
            raise ValueError(
                f"no accepted suggestions in batch {batch_id} — "
                "accept at least one suggestion before applying"
            )

        workspace_id = self._workspace_id or suggestions[0].workspace_id
        work_item_id = suggestions[0].work_item_id

        # WU-3: optimistic-concurrency guard. Suggestions are generated against
        # a specific WorkItemVersion snapshot (``version_number_target``). If
        # the work item has advanced since, applying would silently overwrite
        # newer content — refuse instead. No prior version → target must be 1
        # (the first batch is what creates v1).
        if to_apply and self._versioning_service is not None:
            target = suggestions[0].version_number_target
            latest = await self._versioning_service.get_latest(
                work_item_id, workspace_id
            )
            current = latest.version_number if latest is not None else 0
            expected = target - 1 if latest is None else target
            if current != expected:
                raise VersionConflictError(
                    f"suggestion batch {batch_id} targets version {target} "
                    f"but work item {work_item_id} is at version {current} "
                    "— suggestions are stale; regenerate or merge manually"
                )

        applied_ids: list[UUID] = []
        for s in to_apply:
            if self._section_service is not None:
                await self._section_service.update_section(
                    section_id=s.section_id,  # type: ignore[arg-type]
                    work_item_id=s.work_item_id,
                    workspace_id=workspace_id,
                    actor_id=actor_id,
                    new_content=s.proposed_content,
                )
            applied_ids.append(s.id)

        if applied_ids:
            await self._suggestion_repo.update_status(applied_ids, SuggestionStatus.APPLIED, now)

        # Create a single batch-apply version record so callers always get a version back
        latest_version: WorkItemVersion | None = None
        if self._versioning_service is not None and applied_ids:
            n = len(applied_ids)
            latest_version = await self._versioning_service.create_version(  # type: ignore[assignment]
                work_item_id=work_item_id,
                workspace_id=workspace_id,
                actor_id=actor_id,
                trigger=VersionTrigger.AI_SUGGESTION,
                actor_type=VersionActorType.AI_SUGGESTION,
                commit_message=f"Applied {n} AI suggestion{'s' if n != 1 else ''} from batch",
            )
        elif self._versioning_service is not None:
            # Nothing new applied — return the current latest
            latest_version = await self._versioning_service.get_latest(  # type: ignore[assignment]
                work_item_id, workspace_id
            )

        logger.info(
            "apply_accepted_batch complete batch_id=%s applied=%d skipped=%d",
            batch_id,
            len(applied_ids),
            skipped,
        )
        return {
            "applied_count": len(applied_ids),
            "skipped_count": skipped,
            "latest_version": latest_version,
        }
