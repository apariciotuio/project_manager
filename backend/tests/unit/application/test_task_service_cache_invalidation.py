"""EP-04 + EP-05 — TaskService cache invalidation tests.

WHEN create_node() is called
THEN completeness:{work_item_id} is deleted from cache

WHEN delete_node() is called
THEN completeness:{work_item_id} is deleted from cache

WHEN split() is called
THEN completeness:{work_item_id} is deleted from cache

WHEN merge() is called
THEN completeness:{work_item_id} is deleted from cache

WHEN no cache is injected
THEN mutations succeed without error (backward-compat)
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.models.task_node import TaskGenerationSource, TaskNode, TaskStatus


class _FakeCache:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str, *, ttl_seconds: int = 60) -> None:
        pass

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


class _FakeNodeRepo:
    def __init__(self) -> None:
        self._store: dict[UUID, TaskNode] = {}

    async def get(self, node_id: UUID) -> TaskNode | None:
        return self._store.get(node_id)

    async def save(self, node: TaskNode) -> TaskNode:
        self._store[node.id] = node
        return node

    async def delete(self, node_id: UUID) -> None:
        self._store.pop(node_id, None)

    async def get_by_work_item(self, work_item_id: UUID) -> list[TaskNode]:
        return [n for n in self._store.values() if n.work_item_id == work_item_id]

    async def get_tree_recursive(self, work_item_id: UUID) -> list[TaskNode]:
        return await self.get_by_work_item(work_item_id)

    async def count_by_work_item(self, work_item_id: UUID) -> int:
        return len(await self.get_by_work_item(work_item_id))


class _FakeDepRepo:
    async def get_by_source(self, source_id: UUID) -> list:
        return []

    async def get(self, dep_id: UUID) -> None:
        return None


class _FakeLinkRepo:
    async def get_by_task(self, task_id: UUID) -> list[UUID]:
        return []

    async def create_bulk(self, task_id: UUID, section_ids: list[UUID]) -> None:
        pass

    async def delete_by_task(self, task_id: UUID) -> None:
        pass


def _svc(cache: _FakeCache | None = None):
    from app.application.services.task_service import TaskService

    return TaskService(
        node_repo=_FakeNodeRepo(),  # type: ignore[arg-type]
        dep_repo=_FakeDepRepo(),  # type: ignore[arg-type]
        link_repo=_FakeLinkRepo(),  # type: ignore[arg-type]
        cache=cache,  # type: ignore[arg-type]
    )


def _cache_key(work_item_id: UUID) -> str:
    return f"completeness:{work_item_id}"


class TestTaskServiceCacheInvalidation:
    @pytest.mark.asyncio
    async def test_create_node_invalidates_cache(self) -> None:
        cache = _FakeCache()
        svc = _svc(cache)
        work_item_id = uuid4()
        actor_id = uuid4()
        await svc.create_node(
            work_item_id=work_item_id,
            parent_id=None,
            title="Task A",
            display_order=1,
            actor_id=actor_id,
        )
        assert _cache_key(work_item_id) in cache.deleted

    @pytest.mark.asyncio
    async def test_delete_node_invalidates_cache(self) -> None:
        cache = _FakeCache()
        node_repo = _FakeNodeRepo()
        from app.application.services.task_service import TaskService

        svc = TaskService(
            node_repo=node_repo,  # type: ignore[arg-type]
            dep_repo=_FakeDepRepo(),  # type: ignore[arg-type]
            link_repo=_FakeLinkRepo(),  # type: ignore[arg-type]
            cache=cache,  # type: ignore[arg-type]
        )
        work_item_id = uuid4()
        # Pre-seed a node directly
        node = TaskNode.create(
            work_item_id=work_item_id,
            parent_id=None,
            title="x",
            display_order=1,
            created_by=uuid4(),
        )
        await node_repo.save(node)

        await svc.delete_node(node.id)
        assert _cache_key(work_item_id) in cache.deleted

    @pytest.mark.asyncio
    async def test_split_invalidates_cache(self) -> None:
        cache = _FakeCache()
        node_repo = _FakeNodeRepo()
        from app.application.services.task_service import TaskService

        svc = TaskService(
            node_repo=node_repo,  # type: ignore[arg-type]
            dep_repo=_FakeDepRepo(),  # type: ignore[arg-type]
            link_repo=_FakeLinkRepo(),  # type: ignore[arg-type]
            cache=cache,  # type: ignore[arg-type]
        )
        work_item_id = uuid4()
        node = TaskNode.create(
            work_item_id=work_item_id,
            parent_id=None,
            title="original",
            display_order=1,
            created_by=uuid4(),
        )
        node.materialized_path = str(node.id)
        await node_repo.save(node)

        await svc.split(task_id=node.id, title_a="A", title_b="B", actor_id=uuid4())
        assert _cache_key(work_item_id) in cache.deleted

    @pytest.mark.asyncio
    async def test_merge_invalidates_cache(self) -> None:
        cache = _FakeCache()
        node_repo = _FakeNodeRepo()
        from app.application.services.task_service import TaskService

        svc = TaskService(
            node_repo=node_repo,  # type: ignore[arg-type]
            dep_repo=_FakeDepRepo(),  # type: ignore[arg-type]
            link_repo=_FakeLinkRepo(),  # type: ignore[arg-type]
            cache=cache,  # type: ignore[arg-type]
        )
        work_item_id = uuid4()
        actor = uuid4()
        n1 = TaskNode.create(work_item_id=work_item_id, parent_id=None, title="n1", display_order=1, created_by=actor)
        n1.materialized_path = str(n1.id)
        n2 = TaskNode.create(work_item_id=work_item_id, parent_id=None, title="n2", display_order=2, created_by=actor)
        n2.materialized_path = str(n2.id)
        await node_repo.save(n1)
        await node_repo.save(n2)

        await svc.merge(source_ids=[n1.id, n2.id], title="merged", actor_id=actor)
        assert _cache_key(work_item_id) in cache.deleted

    @pytest.mark.asyncio
    async def test_create_node_no_cache_no_error(self) -> None:
        svc = _svc(cache=None)
        work_item_id = uuid4()
        # Should not raise
        await svc.create_node(
            work_item_id=work_item_id,
            parent_id=None,
            title="Task",
            display_order=1,
            actor_id=uuid4(),
        )
