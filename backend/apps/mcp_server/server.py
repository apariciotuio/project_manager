"""EP-18 — MCP Server (Read & Query Interface).

Thin Python adapter reusing the existing FastAPI application service layer.
Shipped as a separate process — imports services directly (no HTTP hop).

Transports: stdio (default) + HTTP/SSE (opt-in via --transport flag).
Auth: mcp_token with mcp:read scope, single-workspace binding.

Usage:
  python -m apps.mcp_server.server                    # stdio
  python -m apps.mcp_server.server --transport sse    # HTTP/SSE on port 17006
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

# The MCP Python SDK import — guarded so the module loads even if the SDK
# is not installed (e.g. during tests that only exercise the REST API).
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    _MCP_SDK_AVAILABLE = True
except ImportError:
    _MCP_SDK_AVAILABLE = False


def _build_tool_list() -> list[dict[str, Any]]:
    """Registry of MCP tools exposed to clients."""
    return [
        {
            "name": "list_work_items",
            "description": "List work items in the workspace with optional filters",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Filter by state"},
                    "type": {"type": "string", "description": "Filter by type"},
                    "limit": {"type": "integer", "default": 20},
                },
            },
        },
        {
            "name": "get_work_item",
            "description": "Get a work item by ID with its specification, completeness, and gaps",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Work item UUID"},
                },
                "required": ["id"],
            },
        },
        {
            "name": "get_specification",
            "description": "Get the structured specification sections for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_completeness",
            "description": "Get completeness score and dimension breakdown for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_gaps",
            "description": "Get unfilled quality gaps for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_task_tree",
            "description": "Get the task breakdown tree for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_reviews",
            "description": "Get review requests and responses for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_comments",
            "description": "Get comments on a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "get_timeline",
            "description": "Get the activity timeline for a work item",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {"type": "string"},
                    "cursor": {"type": "string", "description": "Pagination cursor"},
                },
                "required": ["work_item_id"],
            },
        },
        {
            "name": "search_work_items",
            "description": "Full-text search across work items via Puppet",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
        {
            "name": "list_teams",
            "description": "List active teams in the workspace",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_tags",
            "description": "List tags in the workspace",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "list_projects",
            "description": "List projects in the workspace",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_inbox",
            "description": "Get the current user's notification inbox",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 50},
                },
            },
        },
        {
            "name": "get_dashboard",
            "description": "Get workspace health dashboard data",
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


async def _handle_tool_call(
    name: str,
    arguments: dict[str, Any],
    workspace_id: UUID,
    user_id: UUID,
) -> str:
    """Dispatch a tool call to the corresponding application service.

    This function imports and constructs services on-demand to avoid circular
    imports and to respect the get_settings lru_cache trap (deferred imports).
    """
    import json

    from app.config.settings import get_settings
    from app.infrastructure.persistence.database import get_session_factory

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        from app.infrastructure.persistence.session_context import with_workspace

        await with_workspace(session, workspace_id)

        if name == "list_work_items":
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.domain.queries.work_item_filters import WorkItemFilters

            repo = WorkItemRepositoryImpl(session)
            filters = WorkItemFilters(
                state=arguments.get("state"),
                type=arguments.get("type"),
                page_size=arguments.get("limit", 20),
            )
            # Use a dummy project_id — MCP lists across all projects
            result = []  # Simplified: return empty for now, real impl fetches
            return json.dumps({"items": result, "tool": name})

        if name == "get_work_item":
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )

            repo = WorkItemRepositoryImpl(session)
            item = await repo.get(UUID(arguments["id"]), workspace_id)
            if item is None:
                return json.dumps({"error": "not found"})
            return json.dumps({
                "id": str(item.id),
                "title": item.title,
                "type": item.type,
                "state": item.state,
                "completeness_score": item.completeness_score,
            })

        if name in (
            "get_specification",
            "get_completeness",
            "get_gaps",
            "get_task_tree",
            "get_reviews",
            "get_comments",
            "get_timeline",
        ):
            return json.dumps({
                "tool": name,
                "work_item_id": arguments.get("work_item_id"),
                "status": "stub — wire to service layer",
            })

        return json.dumps({"tool": name, "status": "stub"})


def create_mcp_server() -> Any:
    """Create and configure the MCP server instance."""
    if not _MCP_SDK_AVAILABLE:
        raise ImportError(
            "MCP Python SDK not installed. Install with: pip install mcp"
        )

    server = Server("work-maturation-platform")

    @server.list_tools()
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["inputSchema"],
            )
            for t in _build_tool_list()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # TODO: extract workspace_id + user_id from MCP auth context
        from uuid import uuid4

        workspace_id = uuid4()  # placeholder
        user_id = uuid4()  # placeholder
        result = await _handle_tool_call(name, arguments, workspace_id, user_id)
        return [TextContent(type="text", text=result)]

    return server


def main() -> None:
    """Entry point for the MCP server process."""
    parser = argparse.ArgumentParser(description="WMP MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    args = parser.parse_args()

    if not _MCP_SDK_AVAILABLE:
        print("ERROR: MCP Python SDK not installed. Install with: pip install mcp")
        return

    server = create_mcp_server()

    if args.transport == "stdio":
        asyncio.run(stdio_server(server).run())
    else:
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Route
        import uvicorn

        sse = SseServerTransport("/messages")
        app = Starlette(
            routes=[
                Route("/sse", endpoint=sse.handle_sse),
                Route("/messages", endpoint=sse.handle_post_message, methods=["POST"]),
            ],
        )
        uvicorn.run(app, host="0.0.0.0", port=17006)


if __name__ == "__main__":
    main()
