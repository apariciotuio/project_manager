"""EP-18 — Unit tests for search_work_items MCP tool handler.

Tests exercise the tool handler in isolation using a fake WorkItemService.
No DB, no MCP SDK import required.

Scenarios:
- 3 items matching query → returns 3 results in expected shape
- limit=2 → returns at most 2 results
- workspace_id mismatch → returns 0 results
- empty query → raises ValueError (maps to -32602)
- blank-only query → raises ValueError
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.pagination import PaginationResult
from apps.mcp_server.tools.search_work_items import (
    SearchWorkItemsInput,
    _build_excerpt,
    handle_search_work_items,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    title: str,
    description: str | None = None,
    workspace_id: UUID | None = None,
    state: WorkItemState = WorkItemState.DRAFT,
    item_type: WorkItemType = WorkItemType.TASK,
) -> WorkItem:
    uid = uuid4()
    return WorkItem.create(
        title=title,
        type=item_type,
        owner_id=uid,
        creator_id=uid,
        project_id=uid,
        description=description,
    )


def _fake_service(items: list[WorkItem]) -> MagicMock:
    """Return a mock WorkItemService whose list_cursor returns the given items."""
    svc = MagicMock()
    svc.list_cursor = AsyncMock(
        return_value=PaginationResult(
            rows=items,
            has_next=False,
            next_cursor=None,
        )
    )
    return svc


WORKSPACE_ID = uuid4()


# ---------------------------------------------------------------------------
# SearchWorkItemsInput validation
# ---------------------------------------------------------------------------


class TestSearchWorkItemsInput:
    def test_valid_input_parsed(self) -> None:
        inp = SearchWorkItemsInput(query="auth", workspace_id=WORKSPACE_ID, limit=5)
        assert inp.query == "auth"
        assert inp.limit == 5

    def test_query_stripped(self) -> None:
        inp = SearchWorkItemsInput(query="  auth flow  ", workspace_id=WORKSPACE_ID)
        assert inp.query == "auth flow"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="query"):
            SearchWorkItemsInput(query="", workspace_id=WORKSPACE_ID)

    def test_blank_only_raises(self) -> None:
        with pytest.raises(ValueError, match="blank"):
            SearchWorkItemsInput(query="   ", workspace_id=WORKSPACE_ID)

    def test_limit_clamped_at_50(self) -> None:
        with pytest.raises(ValueError):
            SearchWorkItemsInput(query="foo", workspace_id=WORKSPACE_ID, limit=51)

    def test_limit_minimum_1(self) -> None:
        with pytest.raises(ValueError):
            SearchWorkItemsInput(query="foo", workspace_id=WORKSPACE_ID, limit=0)

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValueError):
            SearchWorkItemsInput(
                query="foo",
                workspace_id=WORKSPACE_ID,
                unknown_field="oops",  # type: ignore[call-arg]
            )


# ---------------------------------------------------------------------------
# handle_search_work_items — result shape
# ---------------------------------------------------------------------------


class TestHandleSearchWorkItemsShape:
    @pytest.mark.asyncio
    async def test_three_matching_items_returns_three_results(self) -> None:
        items = [
            _make_item("Auth login flow"),
            _make_item("Auth token refresh"),
            _make_item("Auth session expiry"),
        ]
        svc = _fake_service(items)

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_result_shape_contains_required_keys(self) -> None:
        item = _make_item("Auth login flow")
        svc = _fake_service([item])

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        assert len(results) == 1
        r = results[0]
        assert set(r.keys()) == {"id", "title", "state", "type", "url", "excerpt"}

    @pytest.mark.asyncio
    async def test_result_id_is_string_uuid(self) -> None:
        item = _make_item("Auth login flow")
        svc = _fake_service([item])

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        UUID(results[0]["id"])  # raises if not valid UUID string

    @pytest.mark.asyncio
    async def test_result_state_and_type_are_strings(self) -> None:
        item = _make_item("Auth login flow")
        svc = _fake_service([item])

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        assert isinstance(results[0]["state"], str)
        assert isinstance(results[0]["type"], str)

    @pytest.mark.asyncio
    async def test_url_contains_item_id(self) -> None:
        item = _make_item("Auth login flow")
        svc = _fake_service([item])

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
            base_url="https://app.example.com",
        )

        assert str(item.id) in results[0]["url"]
        assert results[0]["url"].startswith("https://app.example.com")

    @pytest.mark.asyncio
    async def test_url_without_base_url_is_relative(self) -> None:
        item = _make_item("Auth login flow")
        svc = _fake_service([item])

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        assert results[0]["url"].startswith("/workspace/items/")


# ---------------------------------------------------------------------------
# handle_search_work_items — limit enforcement
# ---------------------------------------------------------------------------


class TestHandleSearchWorkItemsLimit:
    @pytest.mark.asyncio
    async def test_limit_2_delegates_page_size_2_to_service(self) -> None:
        items = [_make_item(f"Auth item {i}") for i in range(2)]
        svc = _fake_service(items)

        results = await handle_search_work_items(
            {"query": "Auth", "workspace_id": str(WORKSPACE_ID), "limit": 2},
            svc,
        )

        # Service called with page_size=2
        svc.list_cursor.assert_called_once()
        call_kwargs = svc.list_cursor.call_args
        assert call_kwargs.kwargs["page_size"] == 2

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_default_limit_is_10(self) -> None:
        svc = _fake_service([])

        await handle_search_work_items(
            {"query": "foo", "workspace_id": str(WORKSPACE_ID)},
            svc,
        )

        call_kwargs = svc.list_cursor.call_args
        assert call_kwargs.kwargs["page_size"] == 10


# ---------------------------------------------------------------------------
# handle_search_work_items — workspace isolation
# ---------------------------------------------------------------------------


class TestHandleSearchWorkItemsWorkspaceIsolation:
    @pytest.mark.asyncio
    async def test_wrong_workspace_returns_no_results(self) -> None:
        """When the repo returns nothing (workspace mismatch), result is empty."""
        svc = _fake_service([])  # repo found nothing for this workspace

        results = await handle_search_work_items(
            {"query": "auth", "workspace_id": str(uuid4())},
            svc,
        )

        assert results == []

    @pytest.mark.asyncio
    async def test_workspace_id_passed_to_service(self) -> None:
        ws = uuid4()
        svc = _fake_service([])

        await handle_search_work_items(
            {"query": "auth", "workspace_id": str(ws)},
            svc,
        )

        call_args = svc.list_cursor.call_args
        # First positional arg is workspace_id
        assert call_args.args[0] == ws


# ---------------------------------------------------------------------------
# handle_search_work_items — invalid input
# ---------------------------------------------------------------------------


class TestHandleSearchWorkItemsInvalidInput:
    @pytest.mark.asyncio
    async def test_empty_query_raises_value_error(self) -> None:
        svc = _fake_service([])

        with pytest.raises(ValueError):
            await handle_search_work_items(
                {"query": "", "workspace_id": str(WORKSPACE_ID)},
                svc,
            )

    @pytest.mark.asyncio
    async def test_missing_query_raises(self) -> None:
        svc = _fake_service([])

        with pytest.raises((ValueError, TypeError, KeyError)):
            await handle_search_work_items(
                {"workspace_id": str(WORKSPACE_ID)},
                svc,
            )

    @pytest.mark.asyncio
    async def test_invalid_workspace_uuid_raises(self) -> None:
        svc = _fake_service([])

        with pytest.raises(ValueError):
            await handle_search_work_items(
                {"query": "auth", "workspace_id": "not-a-uuid"},
                svc,
            )

    @pytest.mark.asyncio
    async def test_service_not_called_on_invalid_input(self) -> None:
        svc = _fake_service([])

        with pytest.raises(ValueError):
            await handle_search_work_items(
                {"query": "", "workspace_id": str(WORKSPACE_ID)},
                svc,
            )

        svc.list_cursor.assert_not_called()


# ---------------------------------------------------------------------------
# _build_excerpt
# ---------------------------------------------------------------------------


class TestBuildExcerpt:
    def test_query_found_in_description_returns_snippet_around_match(self) -> None:
        item = _make_item("Title", description="The authentication flow needs improvement for login")
        excerpt = _build_excerpt(item, "authentication")
        assert "authentication" in excerpt

    def test_query_not_found_returns_first_120_chars_of_description(self) -> None:
        desc = "x" * 200
        item = _make_item("Title", description=desc)
        excerpt = _build_excerpt(item, "zzz")
        assert excerpt == desc[:120]

    def test_no_description_falls_back_to_title(self) -> None:
        item = _make_item("Auth flow")
        excerpt = _build_excerpt(item, "Auth")
        assert "Auth" in excerpt

    def test_ellipsis_added_when_context_truncated(self) -> None:
        long_desc = "a" * 50 + "target" + "b" * 200
        item = _make_item("Title", description=long_desc)
        excerpt = _build_excerpt(item, "target")
        assert "..." in excerpt
