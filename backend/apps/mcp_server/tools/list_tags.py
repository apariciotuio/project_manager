"""EP-18 — list_tags MCP tool handler.

Returns tags for the bound workspace.
Workspace isolation is enforced by passing workspace_id into the repository
query — never trusting caller-supplied workspace params.

Default: include_archived=False (active tags only).
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class ITagRepoProtocol(Protocol):
    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Any]: ...
    async def list_all_for_workspace(self, workspace_id: UUID) -> list[Any]: ...


def _serialize_tag(tag: Any) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "name": tag.name,
        "color": tag.color,
        "archived": tag.is_archived,
    }


async def handle_list_tags(
    arguments: dict[str, Any],
    tag_repo: ITagRepoProtocol,
    workspace_id: UUID,
) -> list[dict[str, Any]]:
    """Execute the list_tags tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Optional: include_archived (bool, default False).
        tag_repo: Injected tag repository implementation.
        workspace_id: Workspace from MCP auth session (never from client args).

    Returns:
        List of tag dicts with keys: id, name, color, archived.
    """
    include_archived: bool = bool(arguments.get("include_archived", False))

    if include_archived:
        tags = await tag_repo.list_all_for_workspace(workspace_id)
    else:
        tags = await tag_repo.list_active_for_workspace(workspace_id)

    return [_serialize_tag(t) for t in tags]
