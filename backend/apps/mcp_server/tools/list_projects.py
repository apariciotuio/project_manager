"""EP-18 — list_projects MCP tool handler.

Returns all active projects in the caller's workspace.
Truncates at 100 entries and sets _truncated: true if more exist.

work_item_count is deferred to 0 in MVP — no COUNT JOIN implemented.
workspace_id comes from the MCP auth session (injected by caller).
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.application.services.project_service import ProjectService

_MAX_PROJECTS = 100


class ProjectSummary(BaseModel):
    """Single project entry returned by list_projects."""

    id: str
    name: str
    description: str | None
    work_item_count: int


async def handle_list_projects(
    *,
    workspace_id: UUID,
    service: ProjectService,
) -> dict[str, Any]:
    """Execute the list_projects tool.

    Args:
        workspace_id: Workspace to list projects for (from MCP auth session).
        service: Injected ProjectService instance.

    Returns:
        Dict with keys:
          - projects: list of ProjectSummary dicts
          - _truncated: True if results were capped at 100 (omitted otherwise)
    """
    all_projects = await service.list_for_workspace(workspace_id)

    truncated = len(all_projects) > _MAX_PROJECTS
    projects = all_projects[:_MAX_PROJECTS]

    summaries = [
        ProjectSummary(
            id=str(p.id),
            name=p.name,
            description=p.description,
            work_item_count=0,  # deferred — no COUNT JOIN in MVP
        ).model_dump()
        for p in projects
    ]

    result: dict[str, Any] = {"projects": summaries}
    if truncated:
        result["_truncated"] = True
    return result
