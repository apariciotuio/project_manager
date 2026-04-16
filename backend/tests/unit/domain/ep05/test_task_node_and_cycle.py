"""EP-05 — TaskNode + cycle detection."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.task_node import (
    PredecessorNotDoneError,
    TaskDependency,
    TaskNode,
    TaskStatus,
)
from app.domain.quality.cycle_detection import has_cycle_after_add


def _task(title: str = "t") -> TaskNode:
    return TaskNode.create(
        work_item_id=uuid4(),
        parent_id=None,
        title=title,
        display_order=1,
        created_by=uuid4(),
    )


class TestTaskNode:
    def test_start_transitions_draft_to_in_progress(self) -> None:
        t = _task()
        assert t.status is TaskStatus.DRAFT
        t.start(uuid4())
        assert t.status is TaskStatus.IN_PROGRESS

    def test_mark_done_blocked_when_predecessor_open(self) -> None:
        t = _task()
        t.start(uuid4())
        with pytest.raises(PredecessorNotDoneError):
            t.mark_done(uuid4(), [TaskStatus.IN_PROGRESS])

    def test_mark_done_ok_when_predecessors_done(self) -> None:
        t = _task()
        t.start(uuid4())
        t.mark_done(uuid4(), [TaskStatus.DONE, TaskStatus.DONE])
        assert t.status is TaskStatus.DONE

    def test_reopen_flips_to_in_progress(self) -> None:
        t = _task()
        t.start(uuid4())
        t.mark_done(uuid4(), [])
        t.reopen(uuid4())
        assert t.status is TaskStatus.IN_PROGRESS


class TestTaskDependency:
    def test_self_dependency_rejected(self) -> None:
        same = uuid4()
        with pytest.raises(ValueError):
            TaskDependency.create(source_id=same, target_id=same, created_by=uuid4())


class TestCycleDetection:
    def test_simple_cycle_detected(self) -> None:
        a, b = uuid4(), uuid4()
        # existing: a depends on b
        # proposed: b depends on a -> creates a<->b cycle
        assert has_cycle_after_add([(a, b)], (b, a)) is True

    def test_linear_chain_no_cycle(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        # a->b, b->c; adding c->a would cycle; adding a->c does not
        assert has_cycle_after_add([(a, b), (b, c)], (a, c)) is False

    def test_indirect_cycle_detected(self) -> None:
        a, b, c = uuid4(), uuid4(), uuid4()
        # a->b, b->c; proposing c->a creates a->b->c->a cycle
        assert has_cycle_after_add([(a, b), (b, c)], (c, a)) is True

    def test_self_edge_is_a_cycle(self) -> None:
        a = uuid4()
        assert has_cycle_after_add([], (a, a)) is True
