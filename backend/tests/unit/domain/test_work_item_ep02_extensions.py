"""Unit tests for WorkItem EP-02 extensions (draft_data, template_id). RED phase."""

from __future__ import annotations

from uuid import uuid4


class TestWorkItemDraftDataExtension:
    def _make_item(self) -> object:
        from app.domain.models.work_item import WorkItem
        from app.domain.value_objects.work_item_type import WorkItemType

        return WorkItem.create(
            title="Test Item",
            type=WorkItemType.BUG,
            owner_id=uuid4(),
            creator_id=uuid4(),
            project_id=uuid4(),
        )

    def test_work_item_has_draft_data_field(self) -> None:
        item = self._make_item()
        # draft_data starts as None
        assert item.draft_data is None  # type: ignore[union-attr]

    def test_work_item_has_template_id_field(self) -> None:
        item = self._make_item()
        assert item.template_id is None  # type: ignore[union-attr]

    def test_draft_data_cleared_on_state_advance_out_of_draft(self) -> None:
        from app.domain.models.work_item import WorkItem
        from app.domain.value_objects.work_item_state import WorkItemState
        from app.domain.value_objects.work_item_type import WorkItemType

        owner_id = uuid4()
        item = WorkItem.create(
            title="Test",
            type=WorkItemType.BUG,
            owner_id=owner_id,
            creator_id=owner_id,
            project_id=uuid4(),
        )
        item.draft_data = {"description": "partial text"}  # type: ignore[union-attr]

        # Transition out of DRAFT state
        item.apply_transition(WorkItemState.IN_CLARIFICATION, owner_id, reason=None)

        # draft_data must be cleared
        assert item.draft_data is None  # type: ignore[union-attr]

    def test_template_id_immutable_after_set(self) -> None:
        """template_id is set at creation and must not change on subsequent apply_transition calls."""
        from app.domain.models.work_item import WorkItem
        from app.domain.value_objects.work_item_state import WorkItemState
        from app.domain.value_objects.work_item_type import WorkItemType

        owner_id = uuid4()
        template_id = uuid4()
        item = WorkItem.create(
            title="Test",
            type=WorkItemType.BUG,
            owner_id=owner_id,
            creator_id=owner_id,
            project_id=uuid4(),
        )
        item.template_id = template_id  # type: ignore[union-attr]

        item.apply_transition(WorkItemState.IN_CLARIFICATION, owner_id, reason=None)

        # template_id unchanged after state transition
        assert item.template_id == template_id  # type: ignore[union-attr]
