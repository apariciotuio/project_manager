"""EP-18 — list_sections MCP tool handler.

Returns all sections for a work item with a 200-char content preview.
Verifies workspace isolation via WorkItemService.get — raises WorkItemNotFoundError
if the item belongs to a different workspace; mapped to {error: "not_found"}.

No repository imports here — only service-layer access.
section_repo is injected separately (WorkItemService does not own sections).
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.application.services.work_item_service import WorkItemService
from app.domain.exceptions import WorkItemNotFoundError

_MAX_PREVIEW = 200


class ISectionRepoProtocol(Protocol):
    """Minimal protocol for section fetching — avoids domain import coupling."""

    async def get_by_work_item(self, work_item_id: UUID) -> list[Any]: ...


def _content_preview(content: str) -> str:
    return content[:_MAX_PREVIEW]


def _is_complete(section: Any) -> bool:
    """A section is complete if it's optional OR has non-empty content."""
    if not section.is_required:
        return True
    return bool((section.content or "").strip())


def _serialize_section(section: Any) -> dict[str, Any]:
    section_type = (
        section.section_type.value
        if hasattr(section.section_type, "value")
        else str(section.section_type)
    )
    return {
        "id": str(section.id),
        "title": section_type,
        "section_type": section_type,
        "completeness": _is_complete(section),
        "content_preview": _content_preview(section.content or ""),
    }


async def handle_list_sections(
    arguments: dict[str, Any],
    service: WorkItemService,
    section_repo: ISectionRepoProtocol,
    workspace_id: UUID,
) -> list[dict[str, Any]] | dict[str, Any]:
    """Execute the list_sections tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Required: work_item_id (UUID string).
        service: Injected WorkItemService instance (for workspace isolation check).
        section_repo: Injected ISectionRepository implementation.
        workspace_id: Workspace from MCP auth session.

    Returns:
        List of section dicts, or {error: "not_found"} if work item not found/wrong workspace.

    Raises:
        ValueError: On invalid UUID format (caller maps to -32602).
    """
    raw_id = arguments["work_item_id"]
    work_item_id = UUID(raw_id)  # raises ValueError on malformed input

    try:
        await service.get(work_item_id, workspace_id)
    except WorkItemNotFoundError:
        return {"error": "not_found"}

    sections_raw = await section_repo.get_by_work_item(work_item_id)
    return [_serialize_section(s) for s in sections_raw]
