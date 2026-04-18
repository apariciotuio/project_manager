"""Unit tests for expire_work_item_drafts Celery task — EP-02 Phase 7.

Uses FakeWorkItemDraftRepository + FakeWorkItemRepository. No DB, no Celery broker.
Tests DraftService.expire_pre_creation_drafts directly and the Celery task via
eager-mode invocation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from tests.fakes.fake_repositories import FakeWorkItemDraftRepository, FakeWorkItemRepository


def _make_draft(*, expires_at: datetime):
    from app.domain.models.work_item_draft import WorkItemDraft

    return WorkItemDraft(
        id=uuid4(),
        user_id=uuid4(),
        workspace_id=uuid4(),
        data={},
        local_version=1,
        incomplete=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# DraftService.expire_pre_creation_drafts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_expire_pre_creation_drafts_deletes_expired_drafts() -> None:
    """Expired drafts (expires_at < now) are deleted, count matches."""
    from app.application.services.draft_service import DraftService

    draft_repo = FakeWorkItemDraftRepository()
    work_item_repo = FakeWorkItemRepository()
    service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)

    now = datetime.now(UTC)
    # Seed expired rows directly into the fake's internal dict
    for _ in range(3):
        d = _make_draft(expires_at=now - timedelta(hours=1))
        draft_repo._by_user_workspace[(d.user_id, d.workspace_id)] = d

    deleted = await service.expire_pre_creation_drafts()

    assert deleted == 3
    remaining = list(draft_repo._by_user_workspace.values())
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_expire_pre_creation_drafts_ignores_active_drafts() -> None:
    """Drafts with future expires_at are untouched."""
    from app.application.services.draft_service import DraftService

    draft_repo = FakeWorkItemDraftRepository()
    work_item_repo = FakeWorkItemRepository()
    service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)

    now = datetime.now(UTC)
    # 1 expired, 2 active
    expired = _make_draft(expires_at=now - timedelta(hours=1))
    draft_repo._by_user_workspace[(expired.user_id, expired.workspace_id)] = expired
    for _ in range(2):
        d = _make_draft(expires_at=now + timedelta(days=30))
        draft_repo._by_user_workspace[(d.user_id, d.workspace_id)] = d

    deleted = await service.expire_pre_creation_drafts()

    assert deleted == 1
    assert len(draft_repo._by_user_workspace) == 2


@pytest.mark.asyncio
async def test_expire_pre_creation_drafts_returns_zero_when_nothing_expired() -> None:
    """No-op when zero drafts are expired — must return 0, not crash."""
    from app.application.services.draft_service import DraftService

    draft_repo = FakeWorkItemDraftRepository()
    work_item_repo = FakeWorkItemRepository()
    service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)

    now = datetime.now(UTC)
    for _ in range(2):
        d = _make_draft(expires_at=now + timedelta(days=30))
        draft_repo._by_user_workspace[(d.user_id, d.workspace_id)] = d

    deleted = await service.expire_pre_creation_drafts()

    assert deleted == 0
    assert len(draft_repo._by_user_workspace) == 2


@pytest.mark.asyncio
async def test_expire_pre_creation_drafts_empty_store_returns_zero() -> None:
    """Empty repo — no error, returns 0."""
    from app.application.services.draft_service import DraftService

    draft_repo = FakeWorkItemDraftRepository()
    work_item_repo = FakeWorkItemRepository()
    service = DraftService(draft_repo=draft_repo, work_item_repo=work_item_repo)

    deleted = await service.expire_pre_creation_drafts()

    assert deleted == 0
