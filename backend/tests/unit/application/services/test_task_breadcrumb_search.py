"""Unit tests for TaskService.get_node_with_breadcrumb and search_tasks — EP-05 Commit 2."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.task_node import TaskGenerationSource, TaskNode
from tests.unit.fakes.fake_task_repositories import (
    FakeTaskDependencyRepository,
    FakeTaskNodeRepository,
    FakeTaskSectionLinkRepository,
)


def _make_node(
    *,
    work_item_id,
    parent_id=None,
    title="Task",
    display_order=0,
    materialized_path="",
) -> TaskNode:
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=parent_id,
        title=title,
        display_order=display_order,
        created_by=uuid4(),
        source=TaskGenerationSource.MANUAL,
    )
    node.materialized_path = materialized_path or str(node.id)
    return node


def _service(node_repo=None, dep_repo=None, link_repo=None):
    from app.application.services.task_service import TaskService

    return TaskService(
        node_repo=node_repo or FakeTaskNodeRepository(),
        dep_repo=dep_repo or FakeTaskDependencyRepository(),
        link_repo=link_repo or FakeTaskSectionLinkRepository(),
    )


# ---------------------------------------------------------------------------
# get_node_with_breadcrumb
# ---------------------------------------------------------------------------


class TestGetNodeWithBreadcrumb:
    @pytest.mark.asyncio
    async def test_root_node_has_empty_breadcrumb(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()
        root = _make_node(work_item_id=wi_id, title="Root", display_order=1)
        root.materialized_path = str(root.id)
        await repo.save(root)

        svc = _service(node_repo=repo)
        result = await svc.get_node_with_breadcrumb(root.id)

        assert result is not None
        node, breadcrumb = result
        assert node.id == root.id
        assert breadcrumb == []

    @pytest.mark.asyncio
    async def test_child_node_has_parent_in_breadcrumb(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()

        root = _make_node(work_item_id=wi_id, title="Root")
        root.materialized_path = str(root.id)
        await repo.save(root)

        child = _make_node(work_item_id=wi_id, parent_id=root.id, title="Child")
        child.materialized_path = f"{root.id}.{child.id}"
        await repo.save(child)

        svc = _service(node_repo=repo)
        result = await svc.get_node_with_breadcrumb(child.id)

        assert result is not None
        node, breadcrumb = result
        assert node.id == child.id
        assert len(breadcrumb) == 1
        assert breadcrumb[0]["id"] == str(root.id)
        assert breadcrumb[0]["title"] == "Root"

    @pytest.mark.asyncio
    async def test_grandchild_node_has_two_in_breadcrumb(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()

        root = _make_node(work_item_id=wi_id, title="Root")
        root.materialized_path = str(root.id)
        await repo.save(root)

        child = _make_node(work_item_id=wi_id, parent_id=root.id, title="Child")
        child.materialized_path = f"{root.id}.{child.id}"
        await repo.save(child)

        grandchild = _make_node(work_item_id=wi_id, parent_id=child.id, title="GrandChild")
        grandchild.materialized_path = f"{root.id}.{child.id}.{grandchild.id}"
        await repo.save(grandchild)

        svc = _service(node_repo=repo)
        result = await svc.get_node_with_breadcrumb(grandchild.id)

        assert result is not None
        _, breadcrumb = result
        assert len(breadcrumb) == 2
        assert breadcrumb[0]["title"] == "Root"
        assert breadcrumb[1]["title"] == "Child"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self) -> None:
        svc = _service()
        result = await svc.get_node_with_breadcrumb(uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# search_tasks
# ---------------------------------------------------------------------------


class TestSearchTasks:
    @pytest.mark.asyncio
    async def test_returns_matching_titles(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()

        for title in ["Fix bug", "Fix tests", "Add feature"]:
            node = _make_node(work_item_id=wi_id, title=title)
            await repo.save(node)

        svc = _service(node_repo=repo)
        results = await svc.search_tasks(work_item_id=wi_id, q="fix")

        assert len(results) == 2
        titles = {r["title"] for r in results}
        assert "Fix bug" in titles
        assert "Fix tests" in titles

    @pytest.mark.asyncio
    async def test_q_less_than_2_chars_returns_empty(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()
        node = _make_node(work_item_id=wi_id, title="Fix bug")
        await repo.save(node)

        svc = _service(node_repo=repo)
        results = await svc.search_tasks(work_item_id=wi_id, q="f")

        assert results == []

    @pytest.mark.asyncio
    async def test_empty_q_returns_empty(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()
        node = _make_node(work_item_id=wi_id, title="Task")
        await repo.save(node)

        svc = _service(node_repo=repo)
        results = await svc.search_tasks(work_item_id=wi_id, q="")

        assert results == []

    @pytest.mark.asyncio
    async def test_scoped_to_work_item(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id_a = uuid4()
        wi_id_b = uuid4()

        node_a = _make_node(work_item_id=wi_id_a, title="Fix something")
        node_b = _make_node(work_item_id=wi_id_b, title="Fix other")
        await repo.save(node_a)
        await repo.save(node_b)

        svc = _service(node_repo=repo)
        results = await svc.search_tasks(work_item_id=wi_id_a, q="fix")

        assert len(results) == 1
        assert results[0]["id"] == str(node_a.id)

    @pytest.mark.asyncio
    async def test_result_shape_has_id_and_title(self) -> None:
        repo = FakeTaskNodeRepository()
        wi_id = uuid4()
        node = _make_node(work_item_id=wi_id, title="Fix something")
        await repo.save(node)

        svc = _service(node_repo=repo)
        results = await svc.search_tasks(work_item_id=wi_id, q="fix")

        assert len(results) == 1
        assert "id" in results[0]
        assert "title" in results[0]
        assert results[0]["title"] == "Fix something"
