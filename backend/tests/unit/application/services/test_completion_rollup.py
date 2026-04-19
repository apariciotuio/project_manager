"""Unit tests for CompletionRollupService — EP-05 Commit 3."""
from __future__ import annotations

from uuid import uuid4

from app.domain.models.task_node import TaskGenerationSource, TaskNode, TaskStatus


def _make_node(
    *,
    work_item_id,
    parent_id=None,
    title="Task",
    display_order=0,
    status: TaskStatus = TaskStatus.DRAFT,
) -> TaskNode:
    node = TaskNode.create(
        work_item_id=work_item_id,
        parent_id=parent_id,
        title=title,
        display_order=display_order,
        created_by=uuid4(),
        source=TaskGenerationSource.MANUAL,
    )
    node.status = status
    node.materialized_path = str(node.id) if parent_id is None else ""
    return node


class TestCompletionRollupService:
    """Test pure rollup computation — no DB, no side effects."""

    def _service(self):
        from app.application.services.completion_rollup_service import CompletionRollupService
        return CompletionRollupService()

    def test_all_descendants_done_gives_rollup_done(self) -> None:
        svc = self._service()
        wi = uuid4()
        parent = _make_node(work_item_id=wi, title="Parent", status=TaskStatus.DRAFT)
        child_a = _make_node(work_item_id=wi, parent_id=parent.id, title="CA", status=TaskStatus.DONE)
        child_b = _make_node(work_item_id=wi, parent_id=parent.id, title="CB", status=TaskStatus.DONE)

        rollup = svc.compute_rollup(parent, [child_a, child_b])
        assert rollup == "done"

    def test_any_in_progress_gives_rollup_in_progress(self) -> None:
        svc = self._service()
        wi = uuid4()
        parent = _make_node(work_item_id=wi, title="Parent")
        child_a = _make_node(work_item_id=wi, parent_id=parent.id, title="CA", status=TaskStatus.IN_PROGRESS)
        child_b = _make_node(work_item_id=wi, parent_id=parent.id, title="CB", status=TaskStatus.DONE)

        rollup = svc.compute_rollup(parent, [child_a, child_b])
        assert rollup == "in_progress"

    def test_mixed_draft_and_done_gives_rollup_draft(self) -> None:
        svc = self._service()
        wi = uuid4()
        parent = _make_node(work_item_id=wi, title="Parent")
        child_a = _make_node(work_item_id=wi, parent_id=parent.id, title="CA", status=TaskStatus.DRAFT)
        child_b = _make_node(work_item_id=wi, parent_id=parent.id, title="CB", status=TaskStatus.DONE)

        rollup = svc.compute_rollup(parent, [child_a, child_b])
        assert rollup == "draft"

    def test_no_descendants_gives_rollup_draft(self) -> None:
        """Leaf node with no children → rollup=draft."""
        svc = self._service()
        wi = uuid4()
        leaf = _make_node(work_item_id=wi, title="Leaf")

        rollup = svc.compute_rollup(leaf, [])
        assert rollup == "draft"

    def test_single_done_descendant_gives_done(self) -> None:
        svc = self._service()
        wi = uuid4()
        parent = _make_node(work_item_id=wi, title="Parent")
        child = _make_node(work_item_id=wi, parent_id=parent.id, title="C", status=TaskStatus.DONE)

        rollup = svc.compute_rollup(parent, [child])
        assert rollup == "done"

    def test_enrich_tree_adds_rollup_status_to_each_node(self) -> None:
        """enrich_tree returns a list of dicts, each with rollup_status added."""
        svc = self._service()
        wi = uuid4()

        parent = _make_node(work_item_id=wi, title="Parent", display_order=0)
        parent.materialized_path = str(parent.id)
        child = _make_node(work_item_id=wi, parent_id=parent.id, title="Child", status=TaskStatus.DONE, display_order=0)
        child.materialized_path = f"{parent.id}.{child.id}"

        all_nodes = [parent, child]
        enriched = svc.enrich_tree(all_nodes)

        # Find the parent's entry
        parent_entry = next(e for e in enriched if e["id"] == str(parent.id))
        child_entry = next(e for e in enriched if e["id"] == str(child.id))

        assert parent_entry["rollup_status"] == "done"   # all children done
        assert child_entry["rollup_status"] == "draft"   # leaf with no children

    def test_in_progress_child_propagates_up(self) -> None:
        """Parent rollup reflects deepest in_progress descendant."""
        svc = self._service()
        wi = uuid4()

        parent = _make_node(work_item_id=wi, title="P", display_order=0)
        parent.materialized_path = str(parent.id)
        child = _make_node(work_item_id=wi, parent_id=parent.id, title="C",
                           status=TaskStatus.IN_PROGRESS, display_order=0)
        child.materialized_path = f"{parent.id}.{child.id}"

        enriched = svc.enrich_tree([parent, child])
        parent_entry = next(e for e in enriched if e["id"] == str(parent.id))
        assert parent_entry["rollup_status"] == "in_progress"
