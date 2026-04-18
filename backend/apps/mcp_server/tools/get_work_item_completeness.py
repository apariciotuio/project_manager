"""EP-18 — get_work_item_completeness MCP tool handler.

Returns completeness score + dimension-level breakdown for a work item.
Delegates to CompletenessService.compute — no direct repo access.

workspace_id comes from the MCP auth session (injected by caller).
LookupError from service (item not found or wrong workspace) maps to {error: "not_found"}.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class ICompletenessServiceProtocol(Protocol):
    """Minimal protocol for completeness computation — avoids circular imports."""

    async def compute(self, work_item_id: UUID, workspace_id: UUID) -> Any: ...


def _serialize_dimension(dim: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": dim.dimension,
        "title": dim.dimension.replace("_", " ").title(),
        "score": dim.score,
        "filled": dim.filled,
    }
    if not dim.filled and dim.message:
        entry["missing_fields"] = [dim.message]
    return entry


async def handle_get_work_item_completeness(
    arguments: dict[str, Any],
    workspace_id: UUID,
    service: ICompletenessServiceProtocol,
) -> dict[str, Any]:
    """Execute the get_work_item_completeness tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Required: work_item_id (UUID string).
        workspace_id: Workspace context (from MCP auth session).
        service: Injected CompletenessService instance.

    Returns:
        Dict with keys:
          - overall_score: int
          - sections: list of {id, title, score, filled, missing_fields?}
        Or {error: "not_found"} if work item not found / wrong workspace.

    Raises:
        ValueError: On invalid UUID format.
        KeyError: If work_item_id is missing.
    """
    raw_id = arguments["work_item_id"]  # KeyError if missing
    work_item_id = UUID(raw_id)  # ValueError if malformed

    try:
        result = await service.compute(work_item_id, workspace_id)
    except LookupError:
        return {"error": "not_found"}

    sections = [_serialize_dimension(d) for d in result.dimensions]

    return {
        "overall_score": result.score,
        "sections": sections,
    }
