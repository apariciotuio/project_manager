"""EP-18 — Unit tests for list_work_items MCP tool handler.

Tests exercise the handler in isolation using a fake WorkItemService.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns items + count + no _truncated when under limit
- Response shape: all expected keys present in each item
- State filter forwarded to service
- Type filter forwarded to service
- Project filter forwarded to service
- Limit capped at 100 (max); default is 50
- _truncated flag set when result has_next=True
- Cross-workspace isolation: service only sees workspace-scoped results
- Empty result returns empty items list
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_type import WorkItemType
from apps.mcp_server.tools.list_work_items import handle_list_work_items

WORKSPACE_ID = uuid4()

_EXPECTED_ITEM_KEYS = {
    "id",
    "title",
    "state",
    "type",
    "priority",
    "owner",
    "project_name",
    "completeness_score",
    "updated_at",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_work_item(title: str = "Test item") -> WorkItem:
    uid = uuid4()
    return WorkItem.create(
        title=title,
        type=WorkItemType.TASK,
        owner_id=uid,
        creator_id=uid,
        project_id=uid,
    )


def _make_pagination_result(
    items: list[WorkItem],
    *,
    has_next: bool = False,
    next_cursor: str | None = None,
) -> MagicMock:
    result = MagicMock()
    result.rows = items
    result.has_next = has_next
    result.next_cursor = next_cursor
    return result


def _fake_service(items: list[WorkItem], *, has_next: bool = False) -> MagicMock:
    svc = MagicMock()
    svc.list_cursor = AsyncMock(return_value=_make_pagination_result(items, has_next=has_next))
    return svc


# ---------------------------------------------------------------------------
# Shape tests
# ---------------------------------------------------------------------------


class TestListWorkItemsShape:
    @pytest.mark.asyncio
    async def test_returns_dict_with_items_and_count(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert "items" in result
        assert "count" in result

    @pytest.mark.asyncio
    async def test_count_matches_items_length(self) -> None:
        items = [_make_work_item(f"Item {i}") for i in range(3)]
        svc = _fake_service(items)

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert result["count"] == 3
        assert len(result["items"]) == 3

    @pytest.mark.asyncio
    async def test_item_has_all_expected_keys(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert result["items"]
        assert set(result["items"][0].keys()) == _EXPECTED_ITEM_KEYS

    @pytest.mark.asyncio
    async def test_id_is_valid_uuid_string(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        UUID(result["items"][0]["id"])  # raises ValueError if not valid UUID string

    @pytest.mark.asyncio
    async def test_state_is_string(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result["items"][0]["state"], str)

    @pytest.mark.asyncio
    async def test_updated_at_is_string(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result["items"][0]["updated_at"], str)

    @pytest.mark.asyncio
    async def test_completeness_score_is_int(self) -> None:
        item = _make_work_item()
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert isinstance(result["items"][0]["completeness_score"], int)


# ---------------------------------------------------------------------------
# Filter tests
# ---------------------------------------------------------------------------


class TestListWorkItemsFilters:
    @pytest.mark.asyncio
    async def test_state_filter_forwarded_to_service(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={"state": "in_progress"},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        filters = call_kwargs.kwargs["filters"]
        assert filters.state == ["in_progress"]

    @pytest.mark.asyncio
    async def test_type_filter_forwarded_to_service(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={"type": "story"},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        filters = call_kwargs.kwargs["filters"]
        assert filters.type == ["story"]

    @pytest.mark.asyncio
    async def test_project_id_filter_forwarded_to_service(self) -> None:
        project_id = uuid4()
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={"project_id": str(project_id)},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        filters = call_kwargs.kwargs["filters"]
        assert filters.project_id == project_id

    @pytest.mark.asyncio
    async def test_no_filters_passes_none_values(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        filters = call_kwargs.kwargs["filters"]
        assert filters.state is None
        assert filters.type is None
        assert filters.project_id is None


# ---------------------------------------------------------------------------
# Limit and truncation tests
# ---------------------------------------------------------------------------


class TestListWorkItemsLimit:
    @pytest.mark.asyncio
    async def test_default_limit_is_50(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        assert call_kwargs.kwargs["page_size"] == 50

    @pytest.mark.asyncio
    async def test_custom_limit_respected(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={"limit": 10},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        assert call_kwargs.kwargs["page_size"] == 10

    @pytest.mark.asyncio
    async def test_limit_clamped_at_100(self) -> None:
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={"limit": 999},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        call_kwargs = svc.list_cursor.call_args
        assert call_kwargs.kwargs["page_size"] == 100

    @pytest.mark.asyncio
    async def test_truncated_flag_absent_when_has_next_false(self) -> None:
        svc = _fake_service([], has_next=False)

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert "_truncated" not in result

    @pytest.mark.asyncio
    async def test_truncated_flag_true_when_has_next_true(self) -> None:
        svc = _fake_service([], has_next=True)

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert result.get("_truncated") is True


# ---------------------------------------------------------------------------
# Empty and workspace isolation tests
# ---------------------------------------------------------------------------


class TestListWorkItemsEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_result_returns_empty_items(self) -> None:
        svc = _fake_service([])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert result["items"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_workspace_id_forwarded_to_service(self) -> None:
        ws = uuid4()
        svc = _fake_service([])

        await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=ws,
        )

        call_args = svc.list_cursor.call_args
        assert call_args.args[0] == ws

    @pytest.mark.asyncio
    async def test_cross_workspace_items_not_returned(self) -> None:
        """Service already enforces workspace isolation; handler only sees scoped results."""
        # Simulate service returning 0 items for the correct workspace
        # (cross-workspace items are filtered at the service/repo level)
        svc = _fake_service([])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        # Service was called with the correct workspace — items from other workspaces
        # are never returned by the service (enforced at the repo level)
        call_args = svc.list_cursor.call_args
        assert call_args.args[0] == WORKSPACE_ID
        assert result["items"] == []

    @pytest.mark.asyncio
    async def test_title_matches_work_item(self) -> None:
        item = _make_work_item("My Feature Story")
        svc = _fake_service([item])

        result = await handle_list_work_items(
            arguments={},
            service=svc,
            workspace_id=WORKSPACE_ID,
        )

        assert result["items"][0]["title"] == "My Feature Story"
