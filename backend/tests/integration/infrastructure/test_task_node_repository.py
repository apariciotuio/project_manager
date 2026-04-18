"""EP-05 — TaskNodeRepositoryImpl + TaskDependencyRepositoryImpl integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.task_node import TaskDependency, TaskGenerationSource, TaskNode
from app.domain.quality.cycle_detection import has_cycle_after_add
from app.infrastructure.persistence.task_node_repository_impl import (
    TaskDependencyRepositoryImpl,
    TaskNodeRepositoryImpl,
)


@pytest_asyncio.fixture
async def db(db_session: AsyncSession) -> AsyncSession:
    return db_session


@pytest_asyncio.fixture
async def user_and_work_item(db: AsyncSession):  # type: ignore[return]
    from app.domain.models.user import User
    from app.domain.models.work_item import WorkItem
    from app.domain.models.workspace import Workspace
    from app.domain.value_objects.work_item_state import WorkItemState
    from app.domain.value_objects.work_item_type import WorkItemType
    from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
    from app.infrastructure.persistence.work_item_repository_impl import WorkItemRepositoryImpl
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl

    email = f"user_{uuid4().hex[:8]}@test.com"
    user = User.from_google_claims(sub=f"sub_{uuid4().hex}", email=email, name="T", picture=None)
    user = await UserRepositoryImpl(db).upsert(user)
    ws = Workspace.create_from_email(email=email, created_by=user.id)
    ws = await WorkspaceRepositoryImpl(db).create(ws)
    item = WorkItem(
        id=uuid4(),
        project_id=uuid4(),
        title="Test work item",
        type=WorkItemType.TASK,
        state=WorkItemState.DRAFT,
        owner_id=user.id,
        creator_id=user.id,
        description=None,
        original_input=None,
        priority=None,
        due_date=None,
        tags=[],
        completeness_score=0,
        parent_work_item_id=None,
        materialized_path="",
        attachment_count=0,
        has_override=False,
        override_justification=None,
        owner_suspended_flag=False,
        draft_data=None,
        template_id=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        deleted_at=None,
        exported_at=None,
        export_reference=None,
    )
    item = await WorkItemRepositoryImpl(db).save(item, ws.id)
    await db.flush()
    return user, item


def _make_node(work_item_id, actor_id, parent_id=None, order=0, title="task"):  # type: ignore[no-untyped-def]
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=parent_id,
        title=title,
        display_order=order,
        created_by=actor_id,
        source=TaskGenerationSource.MANUAL,
    )
    if parent_id is None:
        node.materialized_path = str(node.id)
    return node


class TestTaskNodeRepository:
    async def test_save_and_get_roundtrip(
        self, db: AsyncSession, user_and_work_item: tuple
    ) -> None:
        user, item = user_and_work_item
        repo = TaskNodeRepositoryImpl(db)
        node = _make_node(item.id, user.id, title="root task")
        await repo.save(node)
        await db.flush()

        found = await repo.get(node.id)
        assert found is not None
        assert found.id == node.id
        assert found.title == "root task"
        assert found.work_item_id == item.id

    async def test_get_by_work_item_returns_all_nodes(
        self, db: AsyncSession, user_and_work_item: tuple
    ) -> None:
        user, item = user_and_work_item
        repo = TaskNodeRepositoryImpl(db)
        n1 = _make_node(item.id, user.id, title="A", order=1)
        n2 = _make_node(item.id, user.id, title="B", order=2)
        await repo.save(n1)
        await repo.save(n2)
        await db.flush()

        nodes = await repo.get_by_work_item(item.id)
        ids = {n.id for n in nodes}
        assert n1.id in ids
        assert n2.id in ids

    async def test_get_tree_recursive_returns_ordered_tree(
        self, db: AsyncSession, user_and_work_item: tuple
    ) -> None:
        user, item = user_and_work_item
        repo = TaskNodeRepositoryImpl(db)

        root = _make_node(item.id, user.id, title="root", order=0)
        await repo.save(root)
        await db.flush()

        child = TaskNode.create(
            work_item_id=item.id,
            parent_id=root.id,
            title="child",
            display_order=0,
            created_by=user.id,
            source=TaskGenerationSource.MANUAL,
        )
        child.materialized_path = f"{root.materialized_path}.{child.id}"
        await repo.save(child)
        await db.flush()

        tree = await repo.get_tree_recursive(item.id)
        assert len(tree) == 2
        ids = [n.id for n in tree]
        # root comes before child in materialized_path order
        assert ids.index(root.id) < ids.index(child.id)

    async def test_delete_removes_node(self, db: AsyncSession, user_and_work_item: tuple) -> None:
        user, item = user_and_work_item
        repo = TaskNodeRepositoryImpl(db)
        node = _make_node(item.id, user.id, title="to delete")
        await repo.save(node)
        await db.flush()

        await repo.delete(node.id)
        await db.flush()

        assert await repo.get(node.id) is None


class TestTaskDependencyRepository:
    async def test_add_and_get_by_source(self, db: AsyncSession, user_and_work_item: tuple) -> None:
        user, item = user_and_work_item
        node_repo = TaskNodeRepositoryImpl(db)
        dep_repo = TaskDependencyRepositoryImpl(db)

        n1 = _make_node(item.id, user.id, title="source")
        n2 = _make_node(item.id, user.id, title="target")
        await node_repo.save(n1)
        await node_repo.save(n2)
        await db.flush()

        dep = TaskDependency.create(source_id=n1.id, target_id=n2.id, created_by=user.id)
        await dep_repo.add(dep)
        await db.flush()

        found = await dep_repo.get_by_source(n1.id)
        assert len(found) == 1
        assert found[0].target_id == n2.id

    async def test_remove_deletes_dependency(
        self, db: AsyncSession, user_and_work_item: tuple
    ) -> None:
        user, item = user_and_work_item
        node_repo = TaskNodeRepositoryImpl(db)
        dep_repo = TaskDependencyRepositoryImpl(db)

        n1 = _make_node(item.id, user.id, title="s")
        n2 = _make_node(item.id, user.id, title="t")
        await node_repo.save(n1)
        await node_repo.save(n2)
        await db.flush()

        dep = TaskDependency.create(source_id=n1.id, target_id=n2.id, created_by=user.id)
        await dep_repo.add(dep)
        await db.flush()

        await dep_repo.remove(dep.id)
        await db.flush()

        assert await dep_repo.get_by_source(n1.id) == []

    async def test_cycle_rejection_via_domain(
        self, db: AsyncSession, user_and_work_item: tuple
    ) -> None:
        """has_cycle_after_add correctly rejects A->B, B->A."""
        user, item = user_and_work_item
        node_repo = TaskNodeRepositoryImpl(db)
        dep_repo = TaskDependencyRepositoryImpl(db)

        a = _make_node(item.id, user.id, title="A")
        b = _make_node(item.id, user.id, title="B")
        await node_repo.save(a)
        await node_repo.save(b)
        await db.flush()

        dep_ab = TaskDependency.create(source_id=a.id, target_id=b.id, created_by=user.id)
        await dep_repo.add(dep_ab)
        await db.flush()

        edges = await dep_repo.get_edges_for_work_item(item.id)
        existing = [(e.source_id, e.target_id) for e in edges]

        # B->A would form A->B->A cycle
        cycle = has_cycle_after_add(existing, (b.id, a.id))
        assert cycle is True

        # B->C (new node) is fine
        c = _make_node(item.id, user.id, title="C")
        await node_repo.save(c)
        await db.flush()
        no_cycle = has_cycle_after_add(existing, (b.id, c.id))
        assert no_cycle is False
