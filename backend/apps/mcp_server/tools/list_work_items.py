"""EP-18 — list_work_items MCP tool handler.

Lists work items in a workspace with optional filters.
Returns a flat summary list — no section bodies.

workspace_id comes from the MCP auth session (injected by caller).
Limit is capped at 100. Default is 50.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.application.services.work_item_service import WorkItemService
from app.domain.queries.work_item_list_filters import WorkItemListFilters

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


class WorkItemSummary(BaseModel):
    """Single work item entry in the list response."""

    id: str
    title: str
    state: str
    type: str
    priority: str | None
    owner: str
    project_name: str | None
    completeness_score: int
    updated_at: str


async def handle_list_work_items(
    arguments: dict[str, Any],
    service: WorkItemService,
    workspace_id: UUID,
) -> dict[str, Any]:
    """Execute the list_work_items tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Optional: state, type, project_id, limit.
        service: Injected WorkItemService instance.
        workspace_id: Workspace to list items for (from MCP auth session).

    Returns:
        Dict with keys:
          - items: list of WorkItemSummary dicts
          - count: number of items returned
          - _truncated: True if more items exist (omitted otherwise)
    """
    raw_limit = arguments.get("limit", _DEFAULT_LIMIT)
    limit = min(int(raw_limit), _MAX_LIMIT)

    state_raw = arguments.get("state")
    type_raw = arguments.get("type")
    project_id_raw = arguments.get("project_id")

    project_id: UUID | None = UUID(project_id_raw) if project_id_raw else None

    filters = WorkItemListFilters(
        state=[state_raw] if state_raw else None,
        type=[type_raw] if type_raw else None,
        project_id=project_id,
    )

    result = await service.list_cursor(
        workspace_id,
        cursor=None,
        page_size=limit,
        filters=filters,
    )

    summaries = []
    for item in result.rows:
        state = item.state.value if hasattr(item.state, "value") else str(item.state)
        item_type = item.type.value if hasattr(item.type, "value") else str(item.type)
        priority = (
            item.priority.value
            if item.priority and hasattr(item.priority, "value")
            else (str(item.priority) if item.priority is not None else None)
        )
        summaries.append(
            WorkItemSummary(
                id=str(item.id),
                title=item.title,
                state=state,
                type=item_type,
                priority=priority,
                owner=str(item.owner_id),
                project_name=None,  # no JOIN in MVP; omit to avoid N+1
                completeness_score=item.completeness_score,
                updated_at=item.updated_at.isoformat(),
            ).model_dump()
        )

    response: dict[str, Any] = {"items": summaries, "count": len(summaries)}
    if result.has_next:
        response["_truncated"] = True
    return response
