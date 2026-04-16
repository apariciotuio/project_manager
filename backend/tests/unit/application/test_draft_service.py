"""Unit tests for DraftService — EP-02 Phase 4.

Uses fake repositories only. No DB/Redis.
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from tests.fakes.fake_repositories import FakeWorkItemDraftRepository, FakeWorkItemRepository


def _make_work_item(state: str = "draft", owner_id=None):
    from app.domain.models.work_item import WorkItem
    from app.domain.value_objects.work_item_type import WorkItemType

    if owner_id is None:
        owner_id = uuid4()
    item = WorkItem.create(
        title="Test Item",
        type=WorkItemType.BUG,
        owner_id=owner_id,
        creator_id=owner_id,
        project_id=uuid4(),
    )
    if state != "draft":
        from app.domain.value_objects.work_item_state import WorkItemState

        state_map = {
            "in_clarification": WorkItemState.IN_CLARIFICATION,
            "in_review": WorkItemState.IN_REVIEW,
        }
        if state in state_map:
            item.state = state_map[state]
    return item


class TestDraftServiceUpsertPreCreation:
    async def test_upsert_new_draft_returns_work_item_draft(self) -> None:
        from app.application.services.draft_service import DraftService

        repo = FakeWorkItemDraftRepository()
        service = DraftService(draft_repo=repo, work_item_repo=FakeWorkItemRepository())

        user_id = uuid4()
        ws_id = uuid4()
        result = await service.upsert_pre_creation_draft(
            user_id=user_id,
            workspace_id=ws_id,
            data={"title": "hello"},
            local_version=0,
        )

        from app.domain.models.work_item_draft import WorkItemDraft

        assert isinstance(result, WorkItemDraft)
        assert result.local_version == 1
        assert result.data == {"title": "hello"}

    async def test_upsert_increments_version_on_matching_version(self) -> None:
        from app.application.services.draft_service import DraftService

        repo = FakeWorkItemDraftRepository()
        service = DraftService(draft_repo=repo, work_item_repo=FakeWorkItemRepository())

        user_id = uuid4()
        ws_id = uuid4()
        r1 = await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={"v": 1}, local_version=0
        )

        from app.domain.models.work_item_draft import WorkItemDraft

        assert isinstance(r1, WorkItemDraft)

        r2 = await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={"v": 2}, local_version=1
        )
        assert isinstance(r2, WorkItemDraft)
        assert r2.local_version == 2

    async def test_upsert_stale_version_returns_draft_conflict(self) -> None:
        from app.application.services.draft_service import DraftService
        from app.domain.value_objects.draft_conflict import DraftConflict

        repo = FakeWorkItemDraftRepository()
        service = DraftService(draft_repo=repo, work_item_repo=FakeWorkItemRepository())

        user_id = uuid4()
        ws_id = uuid4()
        # Server ends up at version 2
        await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={"v": 1}, local_version=0
        )
        await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={"v": 2}, local_version=1
        )

        # Client still thinks version is 1 → conflict
        result = await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={"v": "stale"}, local_version=1
        )
        assert isinstance(result, DraftConflict)
        assert result.server_version == 2
        assert result.server_data == {"v": 2}


class TestDraftServiceSaveCommittedDraft:
    async def test_save_committed_draft_updates_draft_data_not_updated_at(self) -> None:
        from app.application.services.draft_service import DraftService

        item_repo = FakeWorkItemRepository()
        ws_id = uuid4()
        owner_id = uuid4()
        item = _make_work_item(owner_id=owner_id)
        await item_repo.save(item, ws_id)
        original_updated_at = item.updated_at

        service = DraftService(
            draft_repo=FakeWorkItemDraftRepository(), work_item_repo=item_repo
        )
        await service.save_committed_draft(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner_id,
            draft_data={"description": "partial draft"},
        )

        saved = await item_repo.get(item.id, ws_id)
        assert saved is not None
        assert saved.draft_data == {"description": "partial draft"}
        # updated_at must NOT change
        assert saved.updated_at == original_updated_at

    async def test_save_committed_draft_on_non_draft_state_raises(self) -> None:
        from app.application.services.draft_service import DraftService
        from app.domain.exceptions import WorkItemInvalidStateError

        item_repo = FakeWorkItemRepository()
        ws_id = uuid4()
        owner_id = uuid4()
        item = _make_work_item(state="in_review", owner_id=owner_id)
        await item_repo.save(item, ws_id)

        service = DraftService(
            draft_repo=FakeWorkItemDraftRepository(), work_item_repo=item_repo
        )
        with pytest.raises(WorkItemInvalidStateError):
            await service.save_committed_draft(
                item_id=item.id,
                workspace_id=ws_id,
                actor_id=owner_id,
                draft_data={"description": "should fail"},
            )

    async def test_save_committed_draft_non_owner_raises(self) -> None:
        from app.application.services.draft_service import DraftService
        from app.domain.exceptions import WorkItemNotFoundError

        item_repo = FakeWorkItemRepository()
        ws_id = uuid4()
        owner_id = uuid4()
        other_user = uuid4()
        item = _make_work_item(owner_id=owner_id)
        await item_repo.save(item, ws_id)

        service = DraftService(
            draft_repo=FakeWorkItemDraftRepository(), work_item_repo=item_repo
        )
        with pytest.raises((WorkItemNotFoundError, PermissionError, Exception)):
            # Non-owner should not be able to save draft — service must enforce authz
            await service.save_committed_draft(
                item_id=item.id,
                workspace_id=ws_id,
                actor_id=other_user,
                draft_data={"description": "unauthorized"},
            )


class TestDraftServiceDiscard:
    async def test_discard_owned_draft_removes_it(self) -> None:
        from app.application.services.draft_service import DraftService

        repo = FakeWorkItemDraftRepository()
        service = DraftService(draft_repo=repo, work_item_repo=FakeWorkItemRepository())

        user_id = uuid4()
        ws_id = uuid4()
        r = await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={}, local_version=0
        )

        from app.domain.models.work_item_draft import WorkItemDraft

        assert isinstance(r, WorkItemDraft)
        await service.discard_pre_creation_draft(user_id=user_id, draft_id=r.id)

        fetched = await repo.get_by_user_workspace(user_id, ws_id)
        assert fetched is None

    async def test_discard_non_owned_draft_raises_forbidden(self) -> None:
        from app.application.services.draft_service import DraftService
        from app.domain.exceptions import DraftForbiddenError

        repo = FakeWorkItemDraftRepository()
        service = DraftService(draft_repo=repo, work_item_repo=FakeWorkItemRepository())

        user_id = uuid4()
        ws_id = uuid4()
        r = await service.upsert_pre_creation_draft(
            user_id=user_id, workspace_id=ws_id, data={}, local_version=0
        )

        from app.domain.models.work_item_draft import WorkItemDraft

        assert isinstance(r, WorkItemDraft)

        other_user = uuid4()
        with pytest.raises(DraftForbiddenError):
            await service.discard_pre_creation_draft(user_id=other_user, draft_id=r.id)
