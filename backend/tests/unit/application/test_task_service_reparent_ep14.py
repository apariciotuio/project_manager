"""EP-14 — TaskService unit tests: reparent with position + reorder_siblings.

RED tests written first. GREEN implemented in task_service.py.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.task_service import (
    InvalidPositionError,
    TaskService,
)
from app.domain.models.task_node import TaskGenerationSource, TaskNode
from tests.unit.fakes.fake_task_repositories import (
    FakeTaskDependencyRepository,
    FakeTaskNodeRepository,
)


def _make_service(node_repo: FakeTaskNodeRepository | None = None) -> TaskService:
    return TaskService(
        node_repo=node_repo or FakeTaskNodeRepository(),
        dep_repo=FakeTaskDependencyRepository(),
    )


def _make_node(
    work_item_id,
    actor_id,
    *,
    parent_id=None,
    order: int = 0,
    title: str = "node",
    mat_path: str = "",
) -> TaskNode:
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=parent_id,
        title=title,
        display_order=order,
        created_by=actor_id,
        source=TaskGenerationSource.MANUAL,
    )
    node.materialized_path = mat_path or str(node.id)
    return node


# ---------------------------------------------------------------------------
# reparent: basic position semantics
# ---------------------------------------------------------------------------


class TestReparentPosition:
    @pytest.mark.asyncio
    async def test_reparent_position_zero_becomes_first(self) -> None:
        """Moving a node into a parent at position=0 sets display_order below existing siblings."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        # Two root siblings at parent=None with orders 0, 1
        a = _make_node(wi, actor, order=0, title="A")
        b = _make_node(wi, actor, order=1, title="B")
        # Node to move (currently under a different parent — use a child parent)
        parent = _make_node(wi, actor, order=0, title="Parent")
        moving = _make_node(
            wi,
            actor,
            parent_id=parent.id,
            order=0,
            title="Moving",
            mat_path=f"{parent.id}.{uuid4()}",
        )
        # Give moving node its own id in path
        moving.materialized_path = f"{parent.id}.{moving.id}"
        for n in (a, b, parent, moving):
            await repo.save(n)

        # Move 'moving' to root (parent_id=None) at position=0
        result = await svc.reparent(
            node_id=moving.id,
            new_parent_id=None,
            position=0,
            actor_id=actor,
        )

        assert result.parent_id is None
        assert result.display_order == 0
        # a and b should have shifted up
        updated_a = await repo.get(a.id)
        updated_b = await repo.get(b.id)
        assert updated_a is not None
        assert updated_b is not None
        assert updated_a.display_order >= 1
        assert updated_b.display_order >= 2

    @pytest.mark.asyncio
    async def test_reparent_position_end_appends(self) -> None:
        """position=N (end) appends after last sibling."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        a = _make_node(wi, actor, order=0, title="A")
        b = _make_node(wi, actor, order=1, title="B")
        # node to move (in its own isolated spot)
        parent = _make_node(wi, actor, order=10, title="OldParent")
        moving = _make_node(wi, actor, parent_id=parent.id, order=0, title="Moving")
        moving.materialized_path = f"{parent.id}.{moving.id}"
        for n in (a, b, parent, moving):
            await repo.save(n)

        result = await svc.reparent(
            node_id=moving.id,
            new_parent_id=None,
            position=2,  # after a and b
            actor_id=actor,
        )

        assert result.parent_id is None
        assert result.display_order == 2

    @pytest.mark.asyncio
    async def test_reparent_without_position_appends_at_end(self) -> None:
        """position=None keeps current behaviour: append at end."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        a = _make_node(wi, actor, order=0, title="A")
        b = _make_node(wi, actor, order=1, title="B")
        parent = _make_node(wi, actor, order=10, title="OldParent")
        moving = _make_node(wi, actor, parent_id=parent.id, order=0, title="Moving")
        moving.materialized_path = f"{parent.id}.{moving.id}"
        for n in (a, b, parent, moving):
            await repo.save(n)

        result = await svc.reparent(
            node_id=moving.id,
            new_parent_id=None,
            position=None,
            actor_id=actor,
        )

        assert result.parent_id is None
        assert result.display_order > b.display_order

    @pytest.mark.asyncio
    async def test_reparent_position_out_of_range_raises(self) -> None:
        """position > len(siblings) → InvalidPositionError (maps to 422)."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        # Only 1 sibling at root
        a = _make_node(wi, actor, order=0, title="A")
        parent = _make_node(wi, actor, order=10, title="OldParent")
        moving = _make_node(wi, actor, parent_id=parent.id, order=0, title="Moving")
        moving.materialized_path = f"{parent.id}.{moving.id}"
        for n in (a, parent, moving):
            await repo.save(n)

        with pytest.raises(InvalidPositionError):
            await svc.reparent(
                node_id=moving.id,
                new_parent_id=None,
                position=5,  # > len([a]) = 1
                actor_id=actor,
            )

    @pytest.mark.asyncio
    async def test_reparent_negative_position_raises(self) -> None:
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        parent = _make_node(wi, actor, order=10, title="OldParent")
        moving = _make_node(wi, actor, parent_id=parent.id, order=0, title="Moving")
        moving.materialized_path = f"{parent.id}.{moving.id}"
        for n in (parent, moving):
            await repo.save(n)

        with pytest.raises(InvalidPositionError):
            await svc.reparent(
                node_id=moving.id,
                new_parent_id=None,
                position=-1,
                actor_id=actor,
            )

    @pytest.mark.asyncio
    async def test_reparent_cross_parent_renumbers_old_siblings(self) -> None:
        """Old siblings under source parent get their orders compacted after removal."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        # Old parent with 3 children: x(0), moving(1), y(2)
        old_parent = _make_node(wi, actor, order=0, title="OldParent")
        x = _make_node(wi, actor, parent_id=old_parent.id, order=0, title="X")
        x.materialized_path = f"{old_parent.id}.{x.id}"
        moving = _make_node(wi, actor, parent_id=old_parent.id, order=1, title="Moving")
        moving.materialized_path = f"{old_parent.id}.{moving.id}"
        y = _make_node(wi, actor, parent_id=old_parent.id, order=2, title="Y")
        y.materialized_path = f"{old_parent.id}.{y.id}"

        # New parent (empty)
        new_parent = _make_node(wi, actor, order=1, title="NewParent")

        for n in (old_parent, x, moving, y, new_parent):
            await repo.save(n)

        result = await svc.reparent(
            node_id=moving.id,
            new_parent_id=new_parent.id,
            position=0,
            actor_id=actor,
        )

        assert result.parent_id == new_parent.id
        assert result.display_order == 0

        # x stays at 0, y drops from 2 to 1
        updated_x = await repo.get(x.id)
        updated_y = await repo.get(y.id)
        assert updated_x is not None and updated_x.display_order == 0
        assert updated_y is not None and updated_y.display_order == 1

    @pytest.mark.asyncio
    async def test_same_parent_reorder_via_reparent(self) -> None:
        """new_parent_id == old_parent_id → pure position reorder."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        parent = _make_node(wi, actor, order=0, title="Parent")
        a = _make_node(wi, actor, parent_id=parent.id, order=0, title="A")
        a.materialized_path = f"{parent.id}.{a.id}"
        b = _make_node(wi, actor, parent_id=parent.id, order=1, title="B")
        b.materialized_path = f"{parent.id}.{b.id}"
        c = _make_node(wi, actor, parent_id=parent.id, order=2, title="C")
        c.materialized_path = f"{parent.id}.{c.id}"

        for n in (parent, a, b, c):
            await repo.save(n)

        # Move c to position 0 (same parent)
        result = await svc.reparent(
            node_id=c.id,
            new_parent_id=parent.id,
            position=0,
            actor_id=actor,
        )

        assert result.display_order == 0
        updated_a = await repo.get(a.id)
        updated_b = await repo.get(b.id)
        assert updated_a is not None and updated_a.display_order == 1
        assert updated_b is not None and updated_b.display_order == 2


# ---------------------------------------------------------------------------
# reorder_siblings: atomic full-list reorder
# ---------------------------------------------------------------------------


class TestReorderSiblings:
    @pytest.mark.asyncio
    async def test_reorder_siblings_happy_path(self) -> None:
        """Full sibling list provided → orders reassigned 0-based."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        parent = _make_node(wi, actor, order=0, title="Parent")
        a = _make_node(wi, actor, parent_id=parent.id, order=0, title="A")
        a.materialized_path = f"{parent.id}.{a.id}"
        b = _make_node(wi, actor, parent_id=parent.id, order=1, title="B")
        b.materialized_path = f"{parent.id}.{b.id}"
        c = _make_node(wi, actor, parent_id=parent.id, order=2, title="C")
        c.materialized_path = f"{parent.id}.{c.id}"

        for n in (parent, a, b, c):
            await repo.save(n)

        nodes = await svc.reorder_siblings(
            work_item_id=wi,
            parent_id=parent.id,
            ordered_ids=[c.id, a.id, b.id],
            actor_id=actor,
        )

        orders = {n.id: n.display_order for n in nodes}
        assert orders[c.id] == 0
        assert orders[a.id] == 1
        assert orders[b.id] == 2

    @pytest.mark.asyncio
    async def test_reorder_siblings_root_level(self) -> None:
        """parent_id=None → reorder root-level siblings."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        a = _make_node(wi, actor, order=0, title="A")
        b = _make_node(wi, actor, order=1, title="B")
        for n in (a, b):
            await repo.save(n)

        nodes = await svc.reorder_siblings(
            work_item_id=wi,
            parent_id=None,
            ordered_ids=[b.id, a.id],
            actor_id=actor,
        )

        orders = {n.id: n.display_order for n in nodes}
        assert orders[b.id] == 0
        assert orders[a.id] == 1

    @pytest.mark.asyncio
    async def test_reorder_siblings_missing_id_raises(self) -> None:
        """If ordered_ids is missing a sibling, reject with ValueError."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        parent = _make_node(wi, actor, order=0, title="Parent")
        a = _make_node(wi, actor, parent_id=parent.id, order=0, title="A")
        a.materialized_path = f"{parent.id}.{a.id}"
        b = _make_node(wi, actor, parent_id=parent.id, order=1, title="B")
        b.materialized_path = f"{parent.id}.{b.id}"

        for n in (parent, a, b):
            await repo.save(n)

        with pytest.raises(ValueError, match="PARTIAL"):
            await svc.reorder_siblings(
                work_item_id=wi,
                parent_id=parent.id,
                ordered_ids=[a.id],  # missing b
                actor_id=actor,
            )

    @pytest.mark.asyncio
    async def test_reorder_siblings_foreign_id_raises(self) -> None:
        """If ordered_ids contains an id not under parent_id, reject with ValueError."""
        wi = uuid4()
        actor = uuid4()
        repo = FakeTaskNodeRepository()
        svc = _make_service(repo)

        parent = _make_node(wi, actor, order=0, title="Parent")
        a = _make_node(wi, actor, parent_id=parent.id, order=0, title="A")
        a.materialized_path = f"{parent.id}.{a.id}"
        other = _make_node(wi, actor, order=5, title="OtherRoot")

        for n in (parent, a, other):
            await repo.save(n)

        with pytest.raises(ValueError):
            await svc.reorder_siblings(
                work_item_id=wi,
                parent_id=parent.id,
                ordered_ids=[a.id, other.id],  # other is not under parent
                actor_id=actor,
            )
