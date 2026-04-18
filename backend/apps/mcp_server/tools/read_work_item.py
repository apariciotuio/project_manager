"""EP-18 — read_work_item MCP tool handler.

Fetches a single work item by ID with full detail for LLM reasoning:
- All scalar fields (state, type, priority, owner, project, completeness, jira key)
- Section bodies (content truncated to 2000 chars per section with "..." marker)

workspace_id enforces isolation — WorkItemService.get raises WorkItemNotFoundError
if the item belongs to a different workspace; we map that to {error: "not_found"}.

No repository imports here — only service-layer access.
section_repo is injected separately (WorkItemService does not own sections).
"""
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.application.services.work_item_service import WorkItemService
from app.domain.exceptions import WorkItemNotFoundError

_MAX_SECTION_CONTENT = 2000
_TRUNCATION_MARKER = "..."


class ISectionRepoProtocol(Protocol):
    """Minimal protocol for section fetching — avoids domain import coupling."""

    async def get_by_work_item(self, work_item_id: UUID) -> list[Any]: ...


def _truncate(content: str) -> str:
    if len(content) <= _MAX_SECTION_CONTENT:
        return content
    return content[:_MAX_SECTION_CONTENT] + _TRUNCATION_MARKER


def _serialize_section(section: Any) -> dict[str, Any]:
    return {
        "id": str(section.id),
        "title": str(section.section_type.value),
        "content_markdown": _truncate(section.content or ""),
    }


async def handle_read_work_item(
    arguments: dict[str, Any],
    service: WorkItemService,
    section_repo: ISectionRepoProtocol,
) -> dict[str, Any]:
    """Execute the read_work_item tool.

    Args:
        arguments: Raw tool arguments dict from MCP client.
                   Required: work_item_id (UUID string), workspace_id (UUID string).
        service: Injected WorkItemService instance.
        section_repo: Injected ISectionRepository implementation.

    Returns:
        Serialized work item dict with sections, or {error: "not_found"}.

    Raises:
        ValueError: On invalid argument format (caller maps to -32602).
    """
    raw_id = arguments["work_item_id"]
    raw_ws = arguments["workspace_id"]

    # Validate UUIDs — raises ValueError on malformed input
    work_item_id = UUID(raw_id)
    workspace_id = UUID(raw_ws)

    try:
        item = await service.get(work_item_id, workspace_id)
    except WorkItemNotFoundError:
        return {"error": "not_found"}

    sections_raw = await section_repo.get_by_work_item(work_item_id)
    sections = [_serialize_section(s) for s in sections_raw]

    state = item.state.value if hasattr(item.state, "value") else str(item.state)
    item_type = item.type.value if hasattr(item.type, "value") else str(item.type)
    priority = item.priority.value if item.priority and hasattr(item.priority, "value") else (
        str(item.priority) if item.priority is not None else None
    )

    return {
        "id": str(item.id),
        "title": item.title,
        "description": item.description,
        "state": state,
        "type": item_type,
        "priority": priority,
        "owner": str(item.owner_id),
        "project": str(item.project_id),
        "completeness_score": item.completeness_score,
        "external_jira_key": item.external_jira_key,
        "sections": sections,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }
