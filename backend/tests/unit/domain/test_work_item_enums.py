"""Unit tests for WorkItem enums and value objects — RED phase."""

from __future__ import annotations

import pytest


class TestWorkItemState:
    @pytest.mark.parametrize(
        "value",
        [
            "draft",
            "in_clarification",
            "in_review",
            "changes_requested",
            "partially_validated",
            "ready",
            "exported",
        ],
    )
    def test_all_values_exist(self, value: str) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        assert WorkItemState(value).value == value

    def test_exactly_seven_values(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        assert len(WorkItemState) == 7

    def test_is_str_subclass(self) -> None:
        from app.domain.value_objects.work_item_state import WorkItemState

        assert isinstance(WorkItemState.DRAFT, str)


class TestWorkItemType:
    @pytest.mark.parametrize(
        "value",
        [
            "idea",
            "bug",
            "enhancement",
            "task",
            "initiative",
            "spike",
            "business_change",
            "requirement",
        ],
    )
    def test_all_values_exist(self, value: str) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        assert WorkItemType(value).value == value

    def test_exactly_ten_values(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        assert len(WorkItemType) == 10

    def test_milestone_and_story_present(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        values = {t.value for t in WorkItemType}
        assert "milestone" in values
        assert "story" in values

    def test_is_str_subclass(self) -> None:
        from app.domain.value_objects.work_item_type import WorkItemType

        assert isinstance(WorkItemType.BUG, str)


class TestDerivedState:
    @pytest.mark.parametrize("value", ["in_progress", "blocked", "ready"])
    def test_all_values_exist(self, value: str) -> None:
        from app.domain.value_objects.derived_state import DerivedState

        assert DerivedState(value).value == value

    def test_exactly_three_values(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState

        assert len(DerivedState) == 3

    def test_is_str_subclass(self) -> None:
        from app.domain.value_objects.derived_state import DerivedState

        assert isinstance(DerivedState.READY, str)


class TestPriority:
    @pytest.mark.parametrize("value", ["low", "medium", "high", "critical"])
    def test_all_values_exist(self, value: str) -> None:
        from app.domain.value_objects.priority import Priority

        assert Priority(value).value == value

    def test_exactly_four_values(self) -> None:
        from app.domain.value_objects.priority import Priority

        assert len(Priority) == 4

    def test_is_str_subclass(self) -> None:
        from app.domain.value_objects.priority import Priority

        assert isinstance(Priority.HIGH, str)


class TestStateTransitionValueObject:
    def test_frozen_immutable(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.state_transition import StateTransition
        from app.domain.value_objects.work_item_state import WorkItemState

        st = StateTransition(
            work_item_id=uuid4(),
            from_state=WorkItemState.DRAFT,
            to_state=WorkItemState.IN_CLARIFICATION,
            actor_id=uuid4(),
            triggered_at=datetime.now(UTC),
            reason=None,
            is_override=False,
            override_justification=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            st.is_override = True  # type: ignore[misc]

    def test_has_all_fields(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.state_transition import StateTransition
        from app.domain.value_objects.work_item_state import WorkItemState

        now = datetime.now(UTC)
        item_id = uuid4()
        actor_id = uuid4()
        st = StateTransition(
            work_item_id=item_id,
            from_state=WorkItemState.IN_REVIEW,
            to_state=WorkItemState.CHANGES_REQUESTED,
            actor_id=actor_id,
            triggered_at=now,
            reason="needs work",
            is_override=True,
            override_justification="shipping today",
        )
        assert st.work_item_id == item_id
        assert st.from_state == WorkItemState.IN_REVIEW
        assert st.to_state == WorkItemState.CHANGES_REQUESTED
        assert st.actor_id == actor_id
        assert st.triggered_at == now
        assert st.reason == "needs work"
        assert st.is_override is True
        assert st.override_justification == "shipping today"

    def test_override_justification_nullable(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.state_transition import StateTransition
        from app.domain.value_objects.work_item_state import WorkItemState

        st = StateTransition(
            work_item_id=uuid4(),
            from_state=WorkItemState.DRAFT,
            to_state=WorkItemState.IN_CLARIFICATION,
            actor_id=uuid4(),
            triggered_at=datetime.now(UTC),
            reason=None,
            is_override=False,
            override_justification=None,
        )
        assert st.override_justification is None


class TestOwnershipRecord:
    def test_frozen_immutable(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.ownership_record import OwnershipRecord

        rec = OwnershipRecord(
            work_item_id=uuid4(),
            previous_owner_id=uuid4(),
            new_owner_id=uuid4(),
            changed_by=uuid4(),
            changed_at=datetime.now(UTC),
            reason=None,
        )
        with pytest.raises((AttributeError, TypeError)):
            rec.reason = "oops"  # type: ignore[misc]

    def test_has_all_fields(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.ownership_record import OwnershipRecord

        now = datetime.now(UTC)
        wi = uuid4()
        prev = uuid4()
        nxt = uuid4()
        by = uuid4()
        rec = OwnershipRecord(
            work_item_id=wi,
            previous_owner_id=prev,
            new_owner_id=nxt,
            changed_by=by,
            changed_at=now,
            reason="handed off",
        )
        assert rec.work_item_id == wi
        assert rec.previous_owner_id == prev
        assert rec.new_owner_id == nxt
        assert rec.changed_by == by
        assert rec.changed_at == now
        assert rec.reason == "handed off"

    def test_reason_nullable(self) -> None:
        from datetime import UTC, datetime
        from uuid import uuid4

        from app.domain.value_objects.ownership_record import OwnershipRecord

        rec = OwnershipRecord(
            work_item_id=uuid4(),
            previous_owner_id=uuid4(),
            new_owner_id=uuid4(),
            changed_by=uuid4(),
            changed_at=datetime.now(UTC),
            reason=None,
        )
        assert rec.reason is None
