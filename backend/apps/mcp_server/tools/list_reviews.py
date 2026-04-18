"""EP-18 — list_reviews MCP tool handler.

Returns pending + recent review requests for a work item.
Verifies workspace isolation via WorkItemService.get — raises WorkItemNotFoundError
if the item belongs to a different workspace; mapped to {error: "not_found"}.

ReviewSummary shape: {id, reviewer_user_or_team, status, kind, created_at, cancelled_at?}
include_resolved (default False): when False, only PENDING requests are returned.
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.domain.exceptions import WorkItemNotFoundError
from app.domain.models.review import ReviewStatus

_RESOLVED_STATUSES = frozenset({ReviewStatus.CLOSED, ReviewStatus.CANCELLED})


class IReviewRepoProtocol(Protocol):
    async def list_for_work_item(self, work_item_id: UUID) -> list[Any]: ...


def _serialize_review(request: Any) -> dict[str, Any]:
    reviewer_user_or_team = (
        str(request.reviewer_id)
        if request.reviewer_id is not None
        else str(request.team_id)
    )
    result: dict[str, Any] = {
        "id": str(request.id),
        "reviewer_user_or_team": reviewer_user_or_team,
        "status": request.status.value if hasattr(request.status, "value") else str(request.status),
        "kind": request.reviewer_type.value if hasattr(request.reviewer_type, "value") else str(request.reviewer_type),
        "created_at": request.requested_at.isoformat(),
    }
    if request.cancelled_at is not None:
        result["cancelled_at"] = request.cancelled_at.isoformat()
    return result


async def handle_list_reviews(
    arguments: dict[str, Any],
    service: Any,
    review_repo: IReviewRepoProtocol,
    workspace_id: UUID,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Execute the list_reviews tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Required: work_item_id (UUID string).
                   Optional: include_resolved (bool, default False).
        service: Injected WorkItemService instance (for workspace isolation check).
        review_repo: Injected IReviewRequestRepository implementation.
        workspace_id: Workspace from MCP auth session.

    Returns:
        List of review dicts, or {error: "not_found"} if work item not found/wrong workspace.

    Raises:
        ValueError: On invalid UUID format (caller maps to -32602).
    """
    raw_id = arguments["work_item_id"]
    work_item_id = UUID(raw_id)  # raises ValueError on malformed input

    include_resolved: bool = bool(arguments.get("include_resolved", False))

    try:
        await service.get(work_item_id, workspace_id)
    except WorkItemNotFoundError:
        return {"error": "not_found"}

    requests_raw = await review_repo.list_for_work_item(work_item_id)

    if not include_resolved:
        requests_raw = [r for r in requests_raw if r.status not in _RESOLVED_STATUSES]

    return [_serialize_review(r) for r in requests_raw]
