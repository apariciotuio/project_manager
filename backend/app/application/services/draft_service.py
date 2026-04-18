"""DraftService — pre-creation and committed-item draft management — EP-02."""

from __future__ import annotations

import logging
from uuid import UUID

from app.domain.exceptions import (
    WorkItemInvalidStateError,
    WorkItemNotFoundError,
)
from app.domain.models.work_item_draft import WorkItemDraft
from app.domain.repositories.work_item_draft_repository import IWorkItemDraftRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.domain.value_objects.draft_conflict import DraftConflict
from app.domain.value_objects.work_item_state import WorkItemState

logger = logging.getLogger(__name__)


class DraftService:
    def __init__(
        self,
        *,
        draft_repo: IWorkItemDraftRepository,
        work_item_repo: IWorkItemRepository,
    ) -> None:
        self._draft_repo = draft_repo
        self._work_item_repo = work_item_repo

    async def upsert_pre_creation_draft(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        data: dict,  # type: ignore[type-arg]
        local_version: int,
    ) -> WorkItemDraft | DraftConflict:
        """Upsert a pre-creation draft with optimistic locking.

        Returns updated WorkItemDraft on success.
        Returns DraftConflict if server version > local_version.
        """
        draft = WorkItemDraft.create(
            user_id=user_id,
            workspace_id=workspace_id,
            data=data,
        )
        result = await self._draft_repo.upsert(draft, expected_version=local_version)

        if isinstance(result, DraftConflict):
            logger.info(
                "draft_conflict user=%s workspace=%s server_version=%d",
                user_id,
                workspace_id,
                result.server_version,
            )
        return result

    async def get_pre_creation_draft(
        self, user_id: UUID, workspace_id: UUID
    ) -> WorkItemDraft | None:
        return await self._draft_repo.get_by_user_workspace(user_id, workspace_id)

    async def discard_pre_creation_draft(self, *, user_id: UUID, draft_id: UUID) -> None:
        """Delete draft. Raises DraftForbiddenError if caller doesn't own it."""
        await self._draft_repo.delete(draft_id, user_id)

    async def save_committed_draft(
        self,
        *,
        item_id: UUID,
        workspace_id: UUID,
        actor_id: UUID,
        draft_data: dict,  # type: ignore[type-arg]
    ) -> None:
        """Write draft_data to a committed work item.

        Only valid for items in DRAFT state. Does NOT update updated_at.
        Raises WorkItemInvalidStateError if item is not in DRAFT state.
        Raises WorkItemNotFoundError if item not found or not owned by actor.
        """
        item = await self._work_item_repo.get(item_id, workspace_id)
        if item is None:
            raise WorkItemNotFoundError(item_id)

        if item.owner_id != actor_id:
            raise WorkItemNotFoundError(item_id)  # existence disclosure prevention

        if item.state != WorkItemState.DRAFT:
            raise WorkItemInvalidStateError(
                item_id=item_id,
                expected_state="draft",
                actual_state=item.state.value,
            )

        # Update draft_data WITHOUT touching updated_at (audit trail must not include auto-saves)
        original_updated_at = item.updated_at
        item.draft_data = draft_data
        item.updated_at = original_updated_at  # restore after dataclass assignment

        await self._work_item_repo.save(item, workspace_id)

    async def expire_pre_creation_drafts(self) -> int:
        """Delete all pre-creation drafts where expires_at < now(). Returns count deleted."""
        return await self._draft_repo.delete_expired()
