"""EP-05 — DependencyService unit tests: add, remove, blocked tasks."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.dependency_service import (
    DependencyCycleError,
    DependencyNotFoundError,
    DependencyService,
)
from app.application.services.task_service import TaskNodeNotFoundError
from app.domain.models.task_node import TaskDependency, TaskGenerationSource, TaskNode, TaskStatus
from tests.unit.fakes.fake_task_repositories import (
    FakeTaskDependencyRepository,
    FakeTaskNodeRepository,
)


def _svc(
    node_repo: FakeTaskNodeRepository | None = None,
    dep_repo: FakeTaskDependencyRepository | None = None,
) -> DependencyService:
    return DependencyService(
        node_repo=node_repo or FakeTaskNodeRepository(),
        dep_repo=dep_repo or FakeTaskDependencyRepository(),
    )


def _node(work_item_id, actor_id, status: TaskStatus = TaskStatus.DRAFT, title="t"):
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=None,
        title=title,
        display_order=0,
        created_by=actor_id,
        source=TaskGenerationSource.MANUAL,
    )
    node.status = status
    node.materialized_path = str(node.id)
    return node


class TestDependencyServiceAdd:
    @pytest.mark.asyncio
    async def test_add_happy_path(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        a = _node(wi, actor, title="A")
        b = _node(wi, actor, title="B")
        await node_repo.save(a)
        await node_repo.save(b)

        dep = await svc.add(source_id=a.id, target_id=b.id, actor_id=actor)
        assert dep.source_id == a.id
        assert dep.target_id == b.id

    @pytest.mark.asyncio
    async def test_add_cycle_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        a = _node(wi, actor, title="A")
        b = _node(wi, actor, title="B")
        await node_repo.save(a)
        await node_repo.save(b)

        await svc.add(source_id=a.id, target_id=b.id, actor_id=actor)

        with pytest.raises(DependencyCycleError):
            await svc.add(source_id=b.id, target_id=a.id, actor_id=actor)

    @pytest.mark.asyncio
    async def test_add_source_not_found_raises(self) -> None:
        svc = _svc()
        with pytest.raises(TaskNodeNotFoundError):
            await svc.add(source_id=uuid4(), target_id=uuid4(), actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_add_target_not_found_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _svc(node_repo=node_repo)

        a = _node(wi, actor, title="A")
        await node_repo.save(a)

        with pytest.raises(TaskNodeNotFoundError):
            await svc.add(source_id=a.id, target_id=uuid4(), actor_id=actor)


class TestDependencyServiceRemove:
    @pytest.mark.asyncio
    async def test_remove_existing_dep(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        a = _node(wi, actor, title="A")
        b = _node(wi, actor, title="B")
        await node_repo.save(a)
        await node_repo.save(b)

        dep = await svc.add(source_id=a.id, target_id=b.id, actor_id=actor)
        await svc.remove(dep.id)

        assert await dep_repo.get(dep.id) is None

    @pytest.mark.asyncio
    async def test_remove_not_found_raises(self) -> None:
        svc = _svc()
        with pytest.raises(DependencyNotFoundError):
            await svc.remove(uuid4())


class TestDependencyServiceGetBlocked:
    @pytest.mark.asyncio
    async def test_blocked_by_in_progress_predecessor(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        pred = _node(wi, actor, status=TaskStatus.IN_PROGRESS, title="pred")
        blocked = _node(wi, actor, status=TaskStatus.DRAFT, title="blocked")
        await node_repo.save(pred)
        await node_repo.save(blocked)

        dep = TaskDependency.create(source_id=blocked.id, target_id=pred.id, created_by=actor)
        await dep_repo.add(dep)

        result = await svc.get_blocked_tasks(wi)
        blocked_ids = {item["id"] for item in result}
        assert blocked.id in blocked_ids

    @pytest.mark.asyncio
    async def test_not_blocked_when_predecessor_done(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        pred = _node(wi, actor, status=TaskStatus.DONE, title="pred")
        candidate = _node(wi, actor, status=TaskStatus.DRAFT, title="candidate")
        await node_repo.save(pred)
        await node_repo.save(candidate)

        dep = TaskDependency.create(source_id=candidate.id, target_id=pred.id, created_by=actor)
        await dep_repo.add(dep)

        result = await svc.get_blocked_tasks(wi)
        assert result == []

    @pytest.mark.asyncio
    async def test_no_dependencies_returns_empty(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _svc(node_repo=node_repo)

        a = _node(wi, actor, title="A")
        await node_repo.save(a)

        result = await svc.get_blocked_tasks(wi)
        assert result == []

    @pytest.mark.asyncio
    async def test_blocked_by_includes_blocker_ids(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        dep_repo = FakeTaskDependencyRepository()
        svc = _svc(node_repo, dep_repo)

        pred1 = _node(wi, actor, status=TaskStatus.IN_PROGRESS, title="p1")
        pred2 = _node(wi, actor, status=TaskStatus.DRAFT, title="p2")
        blocked = _node(wi, actor, status=TaskStatus.DRAFT, title="b")
        await node_repo.save(pred1)
        await node_repo.save(pred2)
        await node_repo.save(blocked)

        dep1 = TaskDependency.create(source_id=blocked.id, target_id=pred1.id, created_by=actor)
        dep2 = TaskDependency.create(source_id=blocked.id, target_id=pred2.id, created_by=actor)
        await dep_repo.add(dep1)
        await dep_repo.add(dep2)

        result = await svc.get_blocked_tasks(wi)
        assert len(result) == 1
        item = result[0]
        assert item["id"] == blocked.id
        assert pred1.id in item["blocked_by"]
        assert pred2.id in item["blocked_by"]
