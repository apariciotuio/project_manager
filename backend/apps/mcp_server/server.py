"""EP-18 — MCP Server (Read & Query Interface).

Thin Python adapter reusing the existing FastAPI application service layer.
Shipped as a separate process — imports services directly (no HTTP hop).

Transports: stdio (default) + HTTP/SSE (opt-in via --transport flag).
Auth: JWT access token supplied via MCP_TOKEN environment variable at server
      startup.  The token is decoded once; workspace_id and user_id are bound
      for the entire process lifetime.  Clients cannot override or spoof these
      values — they are never accepted as tool arguments.

Usage:
  MCP_TOKEN=<jwt> python -m apps.mcp_server.server           # stdio
  MCP_TOKEN=<jwt> python -m apps.mcp_server.server --transport sse
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def load_auth_context_from_env() -> tuple[UUID, UUID]:
    """Parse MCP_TOKEN env var and return (workspace_id, user_id).

    Raises:
        OSError: MCP_TOKEN not set.
        ValueError: token is expired, invalid, or missing required claims.
    """
    token = os.environ.get("MCP_TOKEN")
    if not token:
        raise OSError(
            "MCP_TOKEN environment variable is required. "
            "Set it to a valid JWT access token before starting the MCP server."
        )
    return _decode_token(token)


def _decode_token(token: str) -> tuple[UUID, UUID]:
    """Decode a JWT and extract (workspace_id, user_id).

    Reads AUTH_JWT_SECRET (and optional AUTH_JWT_* overrides) directly from
    the environment to avoid the get_settings() lru_cache trap at process
    startup.  The sentinel default matches AuthSettings so the dev default
    works without extra configuration.
    """
    from app.infrastructure.adapters.jwt_adapter import (
        JwtAdapter,
        TokenExpiredError,
        TokenInvalidError,
    )

    _SENTINEL = "change-me-in-prod-use-32-chars-or-more-please"
    secret = os.environ.get("AUTH_JWT_SECRET", _SENTINEL)
    algorithm = os.environ.get("AUTH_JWT_ALGORITHM", "HS256")
    issuer = os.environ.get("AUTH_JWT_ISSUER", "wmp")
    audience = os.environ.get("AUTH_JWT_AUDIENCE", "wmp-web")

    adapter = JwtAdapter(secret=secret, algorithm=algorithm, issuer=issuer, audience=audience)
    try:
        claims = adapter.decode(token)
    except TokenExpiredError as exc:
        raise ValueError(f"MCP_TOKEN has expired: {exc}") from exc
    except TokenInvalidError as exc:
        raise ValueError(f"MCP_TOKEN is invalid: {exc}") from exc

    raw_ws = claims.get("workspace_id")
    if not raw_ws:
        raise ValueError(
            "MCP_TOKEN is missing required 'workspace_id' claim. "
            "The token must be issued for a workspace member."
        )
    try:
        workspace_id = UUID(raw_ws)
        user_id = UUID(claims["sub"])
    except (KeyError, ValueError) as exc:
        raise ValueError(f"MCP_TOKEN contains malformed claims: {exc}") from exc

    return workspace_id, user_id


def _resolve_auth_context() -> tuple[UUID, UUID]:
    """Return (workspace_id, user_id) from MCP_TOKEN.

    Thin alias for load_auth_context_from_env; kept separate so tests can
    patch this single call site inside create_mcp_server without importing
    the full settings stack.
    """
    return load_auth_context_from_env()

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
                    "project_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Filter by project UUID",
                    },
                    "limit": {
                        "type": "integer",
                        "maximum": 100,
                        "default": 50,
                        "description": "Maximum number of results (capped at 100)",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "list_sections",
            "description": (
                "List all specification sections for a work item. "
                "Returns id, title, section_type, completeness flag, and first 200 chars of content."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the work item",
                    },
                },
                "required": ["work_item_id"],
                "additionalProperties": False,
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
            "name": "read_work_item",
            "description": (
                "Fetch a single work item by ID with full detail: scalar fields, "
                "all section bodies (truncated to 2000 chars each), completeness score, "
                "and Jira key. Use this to deeply reason about a specific item."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the work item to fetch",
                    },
                },
                "required": ["work_item_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "create_work_item_draft",
            "description": (
                "Create a pre-creation WorkItemDraft in the workspace. "
                "Draft is a floating intake entity — not yet a committed work item."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 200,
                        "description": "Draft title (3-200 chars)",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description",
                    },
                    "type": {
                        "type": "string",
                        "description": "Optional work item type hint",
                    },
                },
                "required": ["title"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_work_item_completeness",
            "description": (
                "Get completeness score and dimension breakdown for a work item. "
                "Returns overall_score and per-dimension sections with missing_fields hints."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the work item",
                    },
                },
                "required": ["work_item_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "search_work_items",
            "description": (
                "Search work items by title/description text within a workspace. "
                "Returns up to `limit` items with id, title, state, type, url, and excerpt."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": "Free-text search term",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                        "description": "Maximum number of results",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
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
            "name": "list_comments",
            "description": (
                "List all comments for a work item. "
                "Returns id, author, body, created_at, resolved flag, and optional section_id. "
                "Optionally filter by section_id."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the work item",
                    },
                    "section_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Optional UUID of the section to filter comments by",
                    },
                },
                "required": ["work_item_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "list_reviews",
            "description": (
                "List review requests for a work item. "
                "By default returns only pending requests. "
                "Set include_resolved=true to include closed and cancelled reviews."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "work_item_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUID of the work item",
                    },
                    "include_resolved": {
                        "type": "boolean",
                        "default": False,
                        "description": "Include closed and cancelled reviews (default: false)",
                    },
                },
                "required": ["work_item_id"],
                "additionalProperties": False,
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

        if name == "create_work_item_draft":
            from apps.mcp_server.tools.create_work_item_draft import handle_create_work_item_draft
            from app.application.services.draft_service import DraftService
            from app.infrastructure.persistence.work_item_draft_repository_impl import (
                WorkItemDraftRepositoryImpl,
            )
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )

            svc = DraftService(
                draft_repo=WorkItemDraftRepositoryImpl(session),
                work_item_repo=WorkItemRepositoryImpl(session),
            )
            result_data = await handle_create_work_item_draft(
                arguments=arguments,
                workspace_id=workspace_id,
                actor_id=user_id,
                service=svc,
            )
            return json.dumps(result_data)

        if name == "get_work_item_completeness":
            from apps.mcp_server.tools.get_work_item_completeness import (
                handle_get_work_item_completeness,
            )
            from app.application.services.completeness_service import CompletenessService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl
            from app.infrastructure.persistence.section_repository_impl import (
                ValidatorRepositoryImpl,
            )

            svc = CompletenessService(
                work_item_repo=WorkItemRepositoryImpl(session),
                section_repo=SectionRepositoryImpl(session),
                validator_repo=ValidatorRepositoryImpl(session),
                cache=_completeness_cache,
            )
            result_data = await handle_get_work_item_completeness(
                arguments=arguments,
                workspace_id=workspace_id,
                service=svc,
            )
            return json.dumps(result_data)

        if name == "list_work_items":
            from apps.mcp_server.tools.list_work_items import handle_list_work_items
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            result_data = await handle_list_work_items(arguments, svc, workspace_id)
            return json.dumps(result_data)

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

        if name == "search_work_items":
            from apps.mcp_server.tools.search_work_items import handle_search_work_items
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            search_args = {**arguments, "workspace_id": str(workspace_id)}
            base_url = settings.frontend_base_url if hasattr(settings, "frontend_base_url") else ""
            results = await handle_search_work_items(search_args, svc, base_url=base_url)
            return json.dumps({"items": results, "count": len(results)})

        if name == "read_work_item":
            from apps.mcp_server.tools.read_work_item import handle_read_work_item
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )
            from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            section_repo = SectionRepositoryImpl(session)
            read_args = {**arguments, "workspace_id": str(workspace_id)}
            result_data = await handle_read_work_item(read_args, svc, section_repo)
            return json.dumps(result_data)

        if name == "list_sections":
            from apps.mcp_server.tools.list_sections import handle_list_sections
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )
            from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            section_repo = SectionRepositoryImpl(session)
            result_data = await handle_list_sections(arguments, svc, section_repo, workspace_id)
            return json.dumps(result_data)

        if name == "list_projects":
            from apps.mcp_server.tools.list_projects import handle_list_projects
            from app.application.services.project_service import ProjectService
            from app.infrastructure.persistence.project_repository_impl import (
                ProjectRepositoryImpl,
                RoutingRuleRepositoryImpl,
            )

            svc = ProjectService(
                project_repo=ProjectRepositoryImpl(session),
                routing_rule_repo=RoutingRuleRepositoryImpl(session),
            )
            result_data = await handle_list_projects(workspace_id=workspace_id, service=svc)
            return json.dumps(result_data)

        if name == "list_comments":
            from apps.mcp_server.tools.list_comments import handle_list_comments
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )
            from app.infrastructure.persistence.comment_repository_impl import CommentRepositoryImpl

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            comment_repo = CommentRepositoryImpl(session)
            result_data = await handle_list_comments(arguments, svc, comment_repo, workspace_id)
            return json.dumps(result_data)

        if name == "list_reviews":
            from apps.mcp_server.tools.list_reviews import handle_list_reviews
            from app.application.services.work_item_service import WorkItemService
            from app.infrastructure.persistence.work_item_repository_impl import (
                WorkItemRepositoryImpl,
            )
            from app.application.services.audit_service import AuditService
            from app.infrastructure.persistence.audit_repository_impl import AuditRepositoryImpl
            from app.application.events.event_bus import EventBus
            from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
            from app.infrastructure.persistence.workspace_membership_repository_impl import (
                WorkspaceMembershipRepositoryImpl,
            )
            from app.infrastructure.persistence.review_repository_impl import (
                ReviewRequestRepositoryImpl,
            )

            svc = WorkItemService(
                work_items=WorkItemRepositoryImpl(session),
                users=UserRepositoryImpl(session),
                memberships=WorkspaceMembershipRepositoryImpl(session),
                audit=AuditService(AuditRepositoryImpl(session)),
                events=EventBus(),
            )
            review_repo = ReviewRequestRepositoryImpl(session)
            result_data = await handle_list_reviews(arguments, svc, review_repo, workspace_id)
            return json.dumps(result_data)

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
    """Create and configure the MCP server instance.

    Auth context (workspace_id, user_id) is resolved once from MCP_TOKEN at server
    startup. Process restart is required to rotate tokens.
    """
    if not _MCP_SDK_AVAILABLE:
        raise ImportError(
            "MCP Python SDK not installed. Install with: pip install mcp"
        )

    # Resolve auth context once at startup; fail fast if token is missing or invalid.
    workspace_id, user_id = _resolve_auth_context()

    # Shared cache instance for completeness computations across tool calls.
    from app.infrastructure.adapters.in_memory_cache_adapter import InMemoryCacheAdapter
    _completeness_cache = InMemoryCacheAdapter()

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
        # workspace_id and user_id are bound at server startup from MCP_TOKEN.
        # Clients cannot override these values — they are never accepted as
        # tool arguments, so cross-workspace access is structurally impossible.
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
