"""Unit tests for wm_breakdown_agent callback — EP-05 Commit 1.

Tests are pure unit tests using FakeTaskNodeRepository so no DB required.
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.domain.models.task_node import TaskNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_payload(work_item_id, breakdown, request_id="req-001") -> dict:
    return {
        "agent": "wm_breakdown_agent",
        "request_id": request_id,
        "status": "success",
        "work_item_id": str(work_item_id),
        "breakdown": breakdown,
    }


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------------------
# Tests for _handle_breakdown logic (extracted / unit-testable)
# ---------------------------------------------------------------------------


class TestBreakdownHandler:
    """Test the _handle_breakdown helper directly — mocks session + service."""

    @pytest.mark.asyncio
    async def test_happy_path_10_nodes(self) -> None:
        """10 flat breakdown items → 10 task nodes created, 0 skipped."""
        from app.presentation.controllers.dundun_callback_controller import _handle_breakdown

        work_item_id = uuid4()
        session = AsyncMock()
        session.execute = AsyncMock()

        # 10 flat items (no parent_title)
        breakdown = [{"title": f"Task {i}"} for i in range(10)]

        nodes_created = []

        async def fake_create_root(**kwargs) -> TaskNode:
            node = TaskNode.create(
                work_item_id=kwargs["work_item_id"],
                parent_id=None,
                title=kwargs["title"],
                display_order=kwargs["display_order"],
                created_by=kwargs["actor_id"],
            )
            node.materialized_path = str(node.id)
            nodes_created.append(node)
            return node

        task_service = AsyncMock()
        task_service.create_node = AsyncMock(side_effect=fake_create_root)

        result = await _handle_breakdown(
            session=session,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            breakdown=breakdown,
            request_id="req-001",
            task_service=task_service,
            actor_id=uuid4(),
        )

        assert result["created_count"] == 10
        assert result["skipped_count"] == 0
        assert task_service.create_node.call_count == 10

    @pytest.mark.asyncio
    async def test_parent_title_resolves_to_child(self) -> None:
        """parent_title set → child created under the parent node."""
        from app.presentation.controllers.dundun_callback_controller import _handle_breakdown

        work_item_id = uuid4()
        session = AsyncMock()

        created_nodes: dict[str, TaskNode] = {}

        async def fake_create_node(**kwargs) -> TaskNode:
            node = TaskNode.create(
                work_item_id=kwargs["work_item_id"],
                parent_id=kwargs.get("parent_id"),
                title=kwargs["title"],
                display_order=kwargs["display_order"],
                created_by=kwargs["actor_id"],
            )
            node.materialized_path = str(node.id)
            created_nodes[kwargs["title"]] = node
            return node

        task_service = AsyncMock()
        task_service.create_node = AsyncMock(side_effect=fake_create_node)

        breakdown = [
            {"title": "Parent"},
            {"title": "Child", "parent_title": "Parent"},
        ]

        result = await _handle_breakdown(
            session=session,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            breakdown=breakdown,
            request_id="req-002",
            task_service=task_service,
            actor_id=uuid4(),
        )

        assert result["created_count"] == 2
        assert result["skipped_count"] == 0

        # The Child should have been created with parent_id = Parent's id
        child_call = [
            c for c in task_service.create_node.call_args_list if c.kwargs.get("title") == "Child"
        ]
        assert len(child_call) == 1
        parent_node = created_nodes["Parent"]
        assert child_call[0].kwargs["parent_id"] == parent_node.id

    @pytest.mark.asyncio
    async def test_nested_parent_chain(self) -> None:
        """A → B → C nested chain resolves correctly."""
        from app.presentation.controllers.dundun_callback_controller import _handle_breakdown

        work_item_id = uuid4()
        session = AsyncMock()

        created_nodes: dict[str, TaskNode] = {}

        async def fake_create_node(**kwargs) -> TaskNode:
            node = TaskNode.create(
                work_item_id=kwargs["work_item_id"],
                parent_id=kwargs.get("parent_id"),
                title=kwargs["title"],
                display_order=kwargs["display_order"],
                created_by=kwargs["actor_id"],
            )
            node.materialized_path = str(node.id)
            created_nodes[kwargs["title"]] = node
            return node

        task_service = AsyncMock()
        task_service.create_node = AsyncMock(side_effect=fake_create_node)

        breakdown = [
            {"title": "A"},
            {"title": "B", "parent_title": "A"},
            {"title": "C", "parent_title": "B"},
        ]

        result = await _handle_breakdown(
            session=session,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            breakdown=breakdown,
            request_id="req-003",
            task_service=task_service,
            actor_id=uuid4(),
        )

        assert result["created_count"] == 3
        c_call = [
            c for c in task_service.create_node.call_args_list if c.kwargs.get("title") == "C"
        ]
        assert c_call[0].kwargs["parent_id"] == created_nodes["B"].id

    @pytest.mark.asyncio
    async def test_unknown_parent_title_falls_back_to_root(self) -> None:
        """parent_title that doesn't resolve → create at root level (no error)."""
        from app.presentation.controllers.dundun_callback_controller import _handle_breakdown

        work_item_id = uuid4()
        session = AsyncMock()

        async def fake_create_node(**kwargs) -> TaskNode:
            node = TaskNode.create(
                work_item_id=kwargs["work_item_id"],
                parent_id=kwargs.get("parent_id"),
                title=kwargs["title"],
                display_order=kwargs["display_order"],
                created_by=kwargs["actor_id"],
            )
            node.materialized_path = str(node.id)
            return node

        task_service = AsyncMock()
        task_service.create_node = AsyncMock(side_effect=fake_create_node)

        breakdown = [
            {"title": "Orphan", "parent_title": "NonExistentParent"},
        ]

        result = await _handle_breakdown(
            session=session,
            work_item_id=work_item_id,
            workspace_id=uuid4(),
            breakdown=breakdown,
            request_id="req-004",
            task_service=task_service,
            actor_id=uuid4(),
        )

        assert result["created_count"] == 1
        assert result["skipped_count"] == 0
        # Should have fallen back to root (parent_id=None)
        call_kwargs = task_service.create_node.call_args_list[0].kwargs
        assert call_kwargs["parent_id"] is None
