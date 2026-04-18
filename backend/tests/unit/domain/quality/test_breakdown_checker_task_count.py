"""EP-04 + EP-05 — BreakdownChecker task_count scoring bands.

Scoring rule (from dimension_checkers module docstring):
  0 tasks   → score 0.0 (not filled)
  1-2 tasks → score 0.4 (partial)
  3-5 tasks → score 0.8 (good)
  6+ tasks  → score 1.0 (filled)

WHEN check_breakdown() is called for an applicable type with task_count=0
THEN result.filled is False AND result.score == 0.0

WHEN check_breakdown() is called for an applicable type with task_count=1
THEN result.filled is False AND result.score == 0.4

WHEN check_breakdown() is called for an applicable type with task_count=2
THEN result.filled is False AND result.score == 0.4

WHEN check_breakdown() is called for an applicable type with task_count=3
THEN result.filled is True AND result.score == 0.8

WHEN check_breakdown() is called for an applicable type with task_count=5
THEN result.filled is True AND result.score == 0.8

WHEN check_breakdown() is called for an applicable type with task_count=6
THEN result.filled is True AND result.score == 1.0

WHEN check_breakdown() is called for an applicable type with task_count=20
THEN result.filled is True AND result.score == 1.0

WHEN check_breakdown() is called for a non-applicable type (Task)
THEN result.applicable is False regardless of task_count
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.quality.dimension_checkers import check_breakdown
from app.domain.value_objects.work_item_type import WorkItemType


class _WI:
    def __init__(self, wi_type: WorkItemType) -> None:
        self.type = wi_type
        self.owner_id = uuid4()
        self.owner_suspended_flag = False


# applicable types for breakdown
_INITIATIVE = _WI(WorkItemType.INITIATIVE)
_BUSINESS_CHANGE = _WI(WorkItemType.BUSINESS_CHANGE)
_TASK = _WI(WorkItemType.TASK)


class TestBreakdownCheckerTaskCount:
    def test_zero_tasks_not_filled(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=0)
        assert result.applicable is True
        assert result.filled is False
        assert result.score == pytest.approx(0.0)

    def test_one_task_partial(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=1)
        assert result.applicable is True
        assert result.filled is False
        assert result.score == pytest.approx(0.4)

    def test_two_tasks_partial(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=2)
        assert result.applicable is True
        assert result.filled is False
        assert result.score == pytest.approx(0.4)

    def test_three_tasks_good(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=3)
        assert result.applicable is True
        assert result.filled is True
        assert result.score == pytest.approx(0.8)

    def test_five_tasks_good(self) -> None:
        result = check_breakdown(_BUSINESS_CHANGE, [], [], task_count=5)
        assert result.applicable is True
        assert result.filled is True
        assert result.score == pytest.approx(0.8)

    def test_six_tasks_fully_filled(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=6)
        assert result.applicable is True
        assert result.filled is True
        assert result.score == pytest.approx(1.0)

    def test_twenty_tasks_fully_filled(self) -> None:
        result = check_breakdown(_INITIATIVE, [], [], task_count=20)
        assert result.applicable is True
        assert result.filled is True
        assert result.score == pytest.approx(1.0)

    def test_not_applicable_type_ignores_task_count(self) -> None:
        result = check_breakdown(_TASK, [], [], task_count=99)
        assert result.applicable is False
        assert result.filled is False
