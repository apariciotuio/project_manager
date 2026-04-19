"""EP-05 — TaskService unit tests: split, merge, reorder, section links."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.task_service import (
    TaskNodeNotFoundError,
    TaskService,
)
from app.domain.models.task_node import TaskGenerationSource, TaskNode
from tests.unit.fakes.fake_task_repositories import (
    FakeTaskDependencyRepository,
    FakeTaskNodeRepository,
    FakeTaskSectionLinkRepository,
)


def _make_service(
    node_repo: FakeTaskNodeRepository | None = None,
    dep_repo: FakeTaskDependencyRepository | None = None,
    link_repo: FakeTaskSectionLinkRepository | None = None,
) -> TaskService:
    return TaskService(
        node_repo=node_repo or FakeTaskNodeRepository(),
        dep_repo=dep_repo or FakeTaskDependencyRepository(),
        link_repo=link_repo or FakeTaskSectionLinkRepository(),
    )


def _root_node(work_item_id, actor_id, order=0, title="root"):
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=None,
        title=title,
        display_order=order,
        created_by=actor_id,
        source=TaskGenerationSource.MANUAL,
    )
    node.materialized_path = str(node.id)
    return node


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------


class TestTaskServiceSplit:
    @pytest.mark.asyncio
    async def test_split_creates_two_siblings_and_deletes_source(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        link_repo = FakeTaskSectionLinkRepository()
        svc = _make_service(node_repo=node_repo, link_repo=link_repo)

        source = _root_node(wi, actor, order=1, title="source")
        await node_repo.save(source)

        a, b = await svc.split(
            task_id=source.id,
            title_a="Part A",
            title_b="Part B",
            actor_id=actor,
        )

        # source is deleted
        assert await node_repo.get(source.id) is None
        # two new nodes under same parent
        assert a.parent_id == source.parent_id
        assert b.parent_id == source.parent_id
        assert a.title == "Part A"
        assert b.title == "Part B"

    @pytest.mark.asyncio
    async def test_split_preserves_display_order(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        source = _root_node(wi, actor, order=2, title="to split")
        await node_repo.save(source)

        a, b = await svc.split(task_id=source.id, title_a="A", title_b="B", actor_id=actor)

        assert a.display_order == 2
        assert b.display_order == 3

    @pytest.mark.asyncio
    async def test_split_copies_section_links(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        link_repo = FakeTaskSectionLinkRepository()
        svc = _make_service(node_repo=node_repo, link_repo=link_repo)

        source = _root_node(wi, actor, title="src")
        await node_repo.save(source)
        section_id = uuid4()
        await link_repo.create_bulk(source.id, [section_id])

        a, b = await svc.split(task_id=source.id, title_a="A", title_b="B", actor_id=actor)

        assert section_id in await link_repo.get_by_task(a.id)
        assert section_id in await link_repo.get_by_task(b.id)

    @pytest.mark.asyncio
    async def test_split_not_found_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(TaskNodeNotFoundError):
            await svc.split(task_id=uuid4(), title_a="A", title_b="B", actor_id=uuid4())

    @pytest.mark.asyncio
    async def test_split_empty_title_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        source = _root_node(wi, actor, title="src")
        await node_repo.save(source)

        with pytest.raises(ValueError):
            await svc.split(task_id=source.id, title_a="", title_b="B", actor_id=actor)


# ---------------------------------------------------------------------------
# merge
# ---------------------------------------------------------------------------


class TestTaskServiceMerge:
    @pytest.mark.asyncio
    async def test_merge_creates_node_deletes_sources(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        link_repo = FakeTaskSectionLinkRepository()
        svc = _make_service(node_repo=node_repo, link_repo=link_repo)

        n1 = _root_node(wi, actor, order=1, title="N1")
        n2 = _root_node(wi, actor, order=2, title="N2")
        await node_repo.save(n1)
        await node_repo.save(n2)

        merged = await svc.merge(
            source_ids=[n1.id, n2.id],
            title="Merged",
            actor_id=actor,
        )

        assert await node_repo.get(n1.id) is None
        assert await node_repo.get(n2.id) is None
        assert merged.title == "Merged"

    @pytest.mark.asyncio
    async def test_merge_takes_min_display_order(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        n1 = _root_node(wi, actor, order=3, title="N1")
        n2 = _root_node(wi, actor, order=1, title="N2")
        await node_repo.save(n1)
        await node_repo.save(n2)

        merged = await svc.merge(source_ids=[n1.id, n2.id], title="M", actor_id=actor)
        assert merged.display_order == 1

    @pytest.mark.asyncio
    async def test_merge_deduplicates_section_links(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        link_repo = FakeTaskSectionLinkRepository()
        svc = _make_service(node_repo=node_repo, link_repo=link_repo)

        n1 = _root_node(wi, actor, order=1, title="N1")
        n2 = _root_node(wi, actor, order=2, title="N2")
        await node_repo.save(n1)
        await node_repo.save(n2)
        sec_shared = uuid4()
        sec_only_n2 = uuid4()
        await link_repo.create_bulk(n1.id, [sec_shared])
        await link_repo.create_bulk(n2.id, [sec_shared, sec_only_n2])

        merged = await svc.merge(source_ids=[n1.id, n2.id], title="M", actor_id=actor)
        merged_sections = await link_repo.get_by_task(merged.id)
        assert set(merged_sections) == {sec_shared, sec_only_n2}

    @pytest.mark.asyncio
    async def test_merge_cross_parent_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        parent_a = _root_node(wi, actor, title="PA")
        parent_b = _root_node(wi, actor, title="PB")
        await node_repo.save(parent_a)
        await node_repo.save(parent_b)

        child_a = TaskNode.create(
            work_item_id=wi, parent_id=parent_a.id, title="CA",
            display_order=1, created_by=actor,
        )
        child_b = TaskNode.create(
            work_item_id=wi, parent_id=parent_b.id, title="CB",
            display_order=1, created_by=actor,
        )
        await node_repo.save(child_a)
        await node_repo.save(child_b)

        with pytest.raises(ValueError, match="parent"):
            await svc.merge(source_ids=[child_a.id, child_b.id], title="M", actor_id=actor)

    @pytest.mark.asyncio
    async def test_merge_single_source_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        n1 = _root_node(wi, actor, title="only")
        await node_repo.save(n1)

        with pytest.raises(ValueError, match="2"):
            await svc.merge(source_ids=[n1.id], title="M", actor_id=actor)

    @pytest.mark.asyncio
    async def test_merge_not_found_raises(self) -> None:
        svc = _make_service()
        with pytest.raises(TaskNodeNotFoundError):
            await svc.merge(source_ids=[uuid4(), uuid4()], title="M", actor_id=uuid4())


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


class TestTaskServiceReorder:
    @pytest.mark.asyncio
    async def test_reorder_updates_display_order(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        n1 = _root_node(wi, actor, order=1, title="N1")
        n2 = _root_node(wi, actor, order=2, title="N2")
        n3 = _root_node(wi, actor, order=3, title="N3")
        await node_repo.save(n1)
        await node_repo.save(n2)
        await node_repo.save(n3)

        # Submit reversed order
        await svc.reorder(work_item_id=wi, ordered_ids=[n3.id, n1.id, n2.id], actor_id=actor)

        assert (await node_repo.get(n3.id)).display_order == 1  # type: ignore[union-attr]
        assert (await node_repo.get(n1.id)).display_order == 2  # type: ignore[union-attr]
        assert (await node_repo.get(n2.id)).display_order == 3  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_reorder_mismatched_parent_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        parent = _root_node(wi, actor, title="parent")
        await node_repo.save(parent)

        root_sibling = _root_node(wi, actor, title="sibling")
        await node_repo.save(root_sibling)

        child = TaskNode.create(
            work_item_id=wi, parent_id=parent.id, title="child",
            display_order=1, created_by=actor,
        )
        await node_repo.save(child)

        with pytest.raises(ValueError, match="parent"):
            await svc.reorder(
                work_item_id=wi,
                ordered_ids=[root_sibling.id, child.id],
                actor_id=actor,
            )

    @pytest.mark.asyncio
    async def test_reorder_id_not_in_work_item_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        node_repo = FakeTaskNodeRepository()
        svc = _make_service(node_repo=node_repo)

        n1 = _root_node(wi, actor, title="N1")
        await node_repo.save(n1)

        with pytest.raises(TaskNodeNotFoundError):
            await svc.reorder(
                work_item_id=wi, ordered_ids=[n1.id, uuid4()], actor_id=actor
            )
