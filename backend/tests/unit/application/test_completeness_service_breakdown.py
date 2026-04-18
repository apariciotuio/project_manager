"""EP-04 + EP-05 — CompletenessService breakdown wiring tests.

WHEN compute() is called for a work item with tasks
THEN it calls task_repo.count_by_work_item() and feeds the result into check_breakdown

WHEN compute() is called and task_repo returns 3
THEN the breakdown dimension score is 0.8

WHEN compute() is called and task_repo returns 0
THEN the breakdown dimension score is 0.0

WHEN compute() is called and task_repo is None (not injected)
THEN breakdown defaults to 0 tasks (backward-compat)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.value_objects.work_item_type import WorkItemType


class _FakeWorkItem:
    def __init__(self, wi_type: WorkItemType = WorkItemType.INITIATIVE) -> None:
        self.type = wi_type
        self.owner_id = uuid4()
        self.owner_suspended_flag = False


class _FakeWorkItemRepo:
    def __init__(self, item: Any) -> None:
        self._item = item

    async def get(self, work_item_id: UUID, workspace_id: UUID) -> Any:
        return self._item


class _FakeSectionRepo:
    async def get_by_work_item(self, work_item_id: UUID) -> list:
        return []


class _FakeValidatorRepo:
    async def get_by_work_item(self, work_item_id: UUID) -> list:
        return []


class _FakeTaskNodeRepo:
    def __init__(self, count: int) -> None:
        self._count = count
        self.called_with: UUID | None = None

    async def count_by_work_item(self, work_item_id: UUID) -> int:
        self.called_with = work_item_id
        return self._count


class _FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, *, ttl_seconds: int = 60) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


def _make_svc(task_count: int | None, wi_type: WorkItemType = WorkItemType.INITIATIVE):
    from app.application.services.completeness_service import CompletenessService

    task_repo = _FakeTaskNodeRepo(task_count) if task_count is not None else None
    return (
        CompletenessService(
            work_item_repo=_FakeWorkItemRepo(_FakeWorkItem(wi_type)),  # type: ignore[arg-type]
            section_repo=_FakeSectionRepo(),  # type: ignore[arg-type]
            validator_repo=_FakeValidatorRepo(),  # type: ignore[arg-type]
            cache=_FakeCache(),  # type: ignore[arg-type]
            task_node_repo=task_repo,  # type: ignore[arg-type]
        ),
        task_repo,
    )


class TestCompletenessServiceBreakdown:
    @pytest.mark.asyncio
    async def test_task_repo_called_with_work_item_id(self) -> None:
        svc, task_repo = _make_svc(3)
        work_item_id = uuid4()
        await svc.compute(work_item_id, uuid4())
        assert task_repo is not None
        assert task_repo.called_with == work_item_id

    @pytest.mark.asyncio
    async def test_three_tasks_breakdown_score_0_8(self) -> None:
        svc, _ = _make_svc(3)
        result = await svc.compute(uuid4(), uuid4())
        breakdown = next(d for d in result.dimensions if d.dimension == "breakdown")
        assert breakdown.applicable is True
        assert breakdown.score == pytest.approx(0.8)
        assert breakdown.filled is True

    @pytest.mark.asyncio
    async def test_zero_tasks_breakdown_score_0(self) -> None:
        svc, _ = _make_svc(0)
        result = await svc.compute(uuid4(), uuid4())
        breakdown = next(d for d in result.dimensions if d.dimension == "breakdown")
        assert breakdown.score == pytest.approx(0.0)
        assert breakdown.filled is False

    @pytest.mark.asyncio
    async def test_no_task_repo_defaults_to_zero(self) -> None:
        """Backward-compat: no task_node_repo → task_count=0."""
        svc, _ = _make_svc(None)
        result = await svc.compute(uuid4(), uuid4())
        breakdown = next(d for d in result.dimensions if d.dimension == "breakdown")
        assert breakdown.score == pytest.approx(0.0)
