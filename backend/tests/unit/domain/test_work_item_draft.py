"""Unit tests for WorkItemDraft domain entity. RED phase — EP-02 Phase 2."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4


class TestWorkItemDraftConstruction:
    def test_create_with_valid_fields(self) -> None:
        from app.domain.models.work_item_draft import WorkItemDraft

        now = datetime.now(UTC)
        draft = WorkItemDraft(
            id=uuid4(),
            user_id=uuid4(),
            workspace_id=uuid4(),
            data={"title": "test", "type": "bug"},
            local_version=1,
            incomplete=True,
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(days=30),
        )

        assert draft.local_version == 1
        assert draft.incomplete is True
        assert draft.data == {"title": "test", "type": "bug"}

    def test_expires_at_defaults_to_30_days_from_now(self) -> None:
        from app.domain.models.work_item_draft import WorkItemDraft

        draft = WorkItemDraft.create(
            user_id=uuid4(),
            workspace_id=uuid4(),
            data={"title": "draft title"},
        )

        expected_expiry = datetime.now(UTC) + timedelta(days=30)
        # Allow 5-second tolerance for test execution time
        assert abs((draft.expires_at - expected_expiry).total_seconds()) < 5

    def test_create_sets_local_version_to_1(self) -> None:
        from app.domain.models.work_item_draft import WorkItemDraft

        draft = WorkItemDraft.create(
            user_id=uuid4(),
            workspace_id=uuid4(),
            data={},
        )

        assert draft.local_version == 1

    def test_create_sets_incomplete_true_by_default(self) -> None:
        from app.domain.models.work_item_draft import WorkItemDraft

        draft = WorkItemDraft.create(
            user_id=uuid4(),
            workspace_id=uuid4(),
            data={},
        )

        assert draft.incomplete is True

    def test_field_types(self) -> None:
        from uuid import UUID

        from app.domain.models.work_item_draft import WorkItemDraft

        draft = WorkItemDraft.create(
            user_id=uuid4(),
            workspace_id=uuid4(),
            data={"nested": {"key": 1}},
        )

        assert isinstance(draft.id, UUID)
        assert isinstance(draft.user_id, UUID)
        assert isinstance(draft.workspace_id, UUID)
        assert isinstance(draft.data, dict)
        assert isinstance(draft.local_version, int)
        assert isinstance(draft.incomplete, bool)
        assert isinstance(draft.created_at, datetime)
        assert isinstance(draft.updated_at, datetime)
        assert isinstance(draft.expires_at, datetime)
