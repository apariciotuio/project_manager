"""EP-18 — list_comments MCP tool handler.

Returns all comments for a work item, optionally filtered by section_id.
Verifies workspace isolation via WorkItemService.get — raises WorkItemNotFoundError
if the item belongs to a different workspace; mapped to {error: "not_found"}.

CommentSummary shape: {id, author, body, created_at, resolved, section_id?}
resolved = True when deleted_at is set (soft-delete = resolved in Comment domain).
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.domain.exceptions import WorkItemNotFoundError


class ICommentRepoProtocol(Protocol):
    async def list_for_work_item(self, work_item_id: UUID) -> list[Any]: ...


def _serialize_comment(comment: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": str(comment.id),
        "author": str(comment.actor_id) if comment.actor_id is not None else None,
        "body": comment.body,
        "created_at": comment.created_at.isoformat(),
        "resolved": comment.deleted_at is not None,
    }
    if comment.anchor_section_id is not None:
        result["section_id"] = str(comment.anchor_section_id)
    return result


async def handle_list_comments(
    arguments: dict[str, Any],
    service: Any,
    comment_repo: ICommentRepoProtocol,
    workspace_id: UUID,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Execute the list_comments tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Required: work_item_id (UUID string).
                   Optional: section_id (UUID string) — filter by anchor section.
        service: Injected WorkItemService instance (for workspace isolation check).
        comment_repo: Injected ICommentRepository implementation.
        workspace_id: Workspace from MCP auth session.

    Returns:
        List of comment dicts, or {error: "not_found"} if work item not found/wrong workspace.

    Raises:
        ValueError: On invalid UUID format (caller maps to -32602).
    """
    raw_id = arguments["work_item_id"]
    work_item_id = UUID(raw_id)  # raises ValueError on malformed input

    section_id: UUID | None = None
    if "section_id" in arguments and arguments["section_id"]:
        section_id = UUID(arguments["section_id"])

    try:
        await service.get(work_item_id, workspace_id)
    except WorkItemNotFoundError:
        return {"error": "not_found"}

    comments_raw = await comment_repo.list_for_work_item(work_item_id)

    if section_id is not None:
        comments_raw = [c for c in comments_raw if c.anchor_section_id == section_id]

    return [_serialize_comment(c) for c in comments_raw]
