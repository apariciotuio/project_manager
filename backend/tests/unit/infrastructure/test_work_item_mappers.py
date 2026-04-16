"""Unit tests for work_item_mapper, state_transition_mapper, ownership_record_mapper.

Round-trip tests: domain → ORM → domain for all enum values and edge fields.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.state_transition import StateTransition
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.persistence.mappers import ownership_record_mapper
from app.infrastructure.persistence.mappers import state_transition_mapper
from app.infrastructure.persistence.mappers import work_item_mapper
from app.infrastructure.persistence.models.orm import (
    OwnershipHistoryORM,
    StateTransitionORM,
    WorkItemORM,
)


def _make_work_item(
    *,
    state: WorkItemState = WorkItemState.DRAFT,
    type: WorkItemType = WorkItemType.BUG,
    priority: Priority | None = None,
    parent_work_item_id: UUID | None = None,
    tags: list[str] | None = None,
) -> WorkItem:
    now = datetime.now(timezone.utc)
    return WorkItem(
        id=uuid4(),
        project_id=uuid4(),
        title="Test item",
        type=type,
        state=state,
        owner_id=uuid4(),
        creator_id=uuid4(),
        description="some desc",
        original_input="raw input",
        priority=priority,
        due_date=date(2026, 6, 1),
        tags=tags if tags is not None else ["a", "b"],
        completeness_score=42,
        parent_work_item_id=parent_work_item_id,
        materialized_path="",
        attachment_count=3,
        has_override=False,
        override_justification=None,
        owner_suspended_flag=False,
        draft_data=None,
        template_id=None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        exported_at=None,
        export_reference=None,
    )


def _make_orm_from_domain(entity: WorkItem, workspace_id: UUID) -> WorkItemORM:
    return work_item_mapper.to_orm(entity, workspace_id=workspace_id)


# ---------------------------------------------------------------------------
# WorkItem mapper round-trips
# ---------------------------------------------------------------------------

class TestWorkItemMapperRoundTrip:
    def test_basic_round_trip(self) -> None:
        ws = uuid4()
        entity = _make_work_item()
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)

        assert result.id == entity.id
        assert result.title == entity.title
        assert result.type == entity.type
        assert result.state == entity.state
        assert result.owner_id == entity.owner_id
        assert result.creator_id == entity.creator_id
        assert result.project_id == entity.project_id
        assert result.description == entity.description
        assert result.original_input == entity.original_input
        assert result.due_date == entity.due_date
        assert result.tags == entity.tags
        assert result.completeness_score == entity.completeness_score
        assert result.attachment_count == entity.attachment_count
        assert result.has_override == entity.has_override
        assert result.owner_suspended_flag == entity.owner_suspended_flag
        assert result.deleted_at == entity.deleted_at
        assert result.exported_at == entity.exported_at
        assert result.export_reference == entity.export_reference

    def test_workspace_id_stored_in_orm_not_domain(self) -> None:
        ws = uuid4()
        entity = _make_work_item()
        orm = _make_orm_from_domain(entity, ws)
        assert orm.workspace_id == ws
        # Domain entity does NOT have workspace_id
        assert not hasattr(work_item_mapper.to_domain(orm), "workspace_id")

    @pytest.mark.parametrize("state", list(WorkItemState))
    def test_all_states_round_trip(self, state: WorkItemState) -> None:
        ws = uuid4()
        entity = _make_work_item(state=state)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.state == state

    @pytest.mark.parametrize("wi_type", list(WorkItemType))
    def test_all_types_round_trip(self, wi_type: WorkItemType) -> None:
        ws = uuid4()
        entity = _make_work_item(type=wi_type)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.type == wi_type

    @pytest.mark.parametrize("prio", list(Priority))
    def test_all_priorities_round_trip(self, prio: Priority) -> None:
        ws = uuid4()
        entity = _make_work_item(priority=prio)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.priority == prio

    def test_null_priority_round_trip(self) -> None:
        ws = uuid4()
        entity = _make_work_item(priority=None)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.priority is None

    def test_null_parent_round_trip(self) -> None:
        ws = uuid4()
        entity = _make_work_item(parent_work_item_id=None)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.parent_work_item_id is None

    def test_parent_set_round_trip(self) -> None:
        ws = uuid4()
        parent_id = uuid4()
        entity = _make_work_item(parent_work_item_id=parent_id)
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.parent_work_item_id == parent_id

    def test_empty_tags_round_trip(self) -> None:
        ws = uuid4()
        entity = _make_work_item(tags=[])
        orm = _make_orm_from_domain(entity, ws)
        result = work_item_mapper.to_domain(orm)
        assert result.tags == []

    def test_apply_to_orm_updates_fields(self) -> None:
        ws = uuid4()
        entity = _make_work_item()
        orm = _make_orm_from_domain(entity, ws)
        entity2 = _make_work_item(state=WorkItemState.IN_CLARIFICATION, priority=Priority.HIGH)
        work_item_mapper.apply_to_orm(entity2, orm, workspace_id=ws)
        assert orm.state == WorkItemState.IN_CLARIFICATION.value
        assert orm.priority == Priority.HIGH.value


# ---------------------------------------------------------------------------
# StateTransition mapper round-trips
# ---------------------------------------------------------------------------

class TestStateTransitionMapperRoundTrip:
    def _make_transition(self, from_state: WorkItemState, to_state: WorkItemState) -> StateTransition:
        return StateTransition(
            work_item_id=uuid4(),
            from_state=from_state,
            to_state=to_state,
            actor_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason="test reason",
            is_override=False,
            override_justification=None,
        )

    def test_basic_round_trip(self) -> None:
        ws = uuid4()
        t = self._make_transition(WorkItemState.DRAFT, WorkItemState.IN_CLARIFICATION)
        orm = state_transition_mapper.to_orm(t, workspace_id=ws)
        result = state_transition_mapper.to_domain(orm)
        assert result.from_state == WorkItemState.DRAFT
        assert result.to_state == WorkItemState.IN_CLARIFICATION
        assert result.actor_id == t.actor_id
        assert result.reason == t.reason
        assert result.is_override is False

    def test_null_from_state_stored_as_none(self) -> None:
        ws = uuid4()
        t = self._make_transition(WorkItemState.DRAFT, WorkItemState.DRAFT)
        orm = state_transition_mapper.to_orm(t, workspace_id=ws, from_state_override=None)
        assert orm.from_state is None

    def test_override_transition(self) -> None:
        ws = uuid4()
        t = StateTransition(
            work_item_id=uuid4(),
            from_state=WorkItemState.IN_CLARIFICATION,
            to_state=WorkItemState.READY,
            actor_id=uuid4(),
            triggered_at=datetime.now(timezone.utc),
            reason=None,
            is_override=True,
            override_justification="urgent release",
        )
        orm = state_transition_mapper.to_orm(t, workspace_id=ws)
        result = state_transition_mapper.to_domain(orm)
        assert result.is_override is True
        assert result.override_justification == "urgent release"

    @pytest.mark.parametrize("state", list(WorkItemState))
    def test_all_to_states(self, state: WorkItemState) -> None:
        ws = uuid4()
        t = self._make_transition(WorkItemState.DRAFT, state)
        orm = state_transition_mapper.to_orm(t, workspace_id=ws)
        result = state_transition_mapper.to_domain(orm)
        assert result.to_state == state


# ---------------------------------------------------------------------------
# OwnershipRecord mapper round-trips
# ---------------------------------------------------------------------------

class TestOwnershipRecordMapperRoundTrip:
    def _make_record(self, *, prev: UUID | None = None) -> OwnershipRecord:
        new_owner = uuid4()
        return OwnershipRecord(
            work_item_id=uuid4(),
            previous_owner_id=prev if prev is not None else uuid4(),
            new_owner_id=new_owner,
            changed_by=uuid4(),
            changed_at=datetime.now(timezone.utc),
            reason="reassign",
        )

    def test_basic_round_trip(self) -> None:
        ws = uuid4()
        prev = uuid4()
        rec = self._make_record(prev=prev)
        orm = ownership_record_mapper.to_orm(rec, workspace_id=ws, previous_owner_id=prev)
        result = ownership_record_mapper.to_domain(orm)
        assert result.new_owner_id == rec.new_owner_id
        assert result.changed_by == rec.changed_by
        assert result.reason == rec.reason
        assert result.previous_owner_id == prev

    def test_null_previous_owner_sentinel(self) -> None:
        ws = uuid4()
        rec = self._make_record()
        orm = ownership_record_mapper.to_orm(rec, workspace_id=ws, previous_owner_id=None)
        result = ownership_record_mapper.to_domain(orm)
        # sentinel: previous_owner_id == new_owner_id when originally NULL
        assert result.previous_owner_id == rec.new_owner_id

    def test_workspace_id_stored_in_orm(self) -> None:
        ws = uuid4()
        rec = self._make_record()
        orm = ownership_record_mapper.to_orm(rec, workspace_id=ws, previous_owner_id=None)
        assert orm.workspace_id == ws
