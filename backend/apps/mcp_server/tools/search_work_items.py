"""EP-18 — search_work_items MCP tool handler.

Delegates to WorkItemService.list_cursor with a q= filter.
Returns a flat list of {id, title, state, type, url, excerpt}.

No repository imports here — only service-layer access.
workspace_id comes from the MCP auth session (injected by caller).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.application.services.work_item_service import WorkItemService
from app.domain.queries.work_item_list_filters import WorkItemListFilters

_MAX_LIMIT = 50
_MIN_Q = 1


class SearchWorkItemsInput(BaseModel):
    """Validated input for search_work_items."""

    model_config = {"extra": "forbid"}

    query: str = Field(..., min_length=_MIN_Q, description="Search query string")
    workspace_id: UUID = Field(..., description="Workspace to search within")
    limit: int = Field(default=10, ge=1, le=_MAX_LIMIT)

    @field_validator("query")
    @classmethod
    def _strip_query(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("query must not be blank")
        return stripped


class WorkItemSearchResult(BaseModel):
    """Single search result item."""

    id: str
    title: str
    state: str
    type: str
    url: str
    excerpt: str


def _build_excerpt(item: Any, query: str) -> str:
    """Build a short excerpt from description or title containing the query term."""
    text = item.description or item.title or ""
    q_lower = query.lower()
    text_lower = text.lower()
    pos = text_lower.find(q_lower)
    if pos == -1:
        return text[:120]
    start = max(0, pos - 40)
    end = min(len(text), pos + len(query) + 80)
    snippet = text[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


async def handle_search_work_items(
    arguments: dict[str, Any],
    service: WorkItemService,
    base_url: str = "",
) -> list[dict[str, Any]]:
    """Execute the search_work_items tool.

    Args:
        arguments: Raw tool arguments dict from the MCP client.
        service: Injected WorkItemService instance.
        base_url: Optional base URL for building item URLs (e.g. https://app.example.com).

    Returns:
        List of serialized WorkItemSearchResult dicts.

    Raises:
        ValueError: On invalid arguments (caller maps to -32602).
    """
    inp = SearchWorkItemsInput(**arguments)

    filters = WorkItemListFilters(q=inp.query, limit=inp.limit)

    result = await service.list_cursor(
        inp.workspace_id,
        cursor=None,
        page_size=inp.limit,
        filters=filters,
    )

    items: list[dict[str, Any]] = []
    for item in result.rows:
        url = f"{base_url}/workspace/items/{item.id}" if base_url else f"/workspace/items/{item.id}"
        excerpt = _build_excerpt(item, inp.query)
        items.append(
            WorkItemSearchResult(
                id=str(item.id),
                title=item.title,
                state=str(item.state.value) if hasattr(item.state, "value") else str(item.state),
                type=str(item.type.value) if hasattr(item.type, "value") else str(item.type),
                url=url,
                excerpt=excerpt,
            ).model_dump()
        )

    return items
