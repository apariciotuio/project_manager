"""EP-09 — SearchService.

Thin wrapper over PuppetClient for workspace-scoped semantic search.
workspace_id is always injected server-side; callers cannot override the category.

Per design.md (supersedes): workspace isolation uses
category = f"wm_{workspace_id}" (legacy/simplified form accepted here).
The full category format from EP-13/EP-18 is
  "tuio-wmp:ws:<workspace_id>:workitem|section|comment"
but we use the simplified form that the existing PuppetClient.search(query, tags)
interface accepts — the tags list is the isolation mechanism.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.ports.puppet import PuppetClient, PuppetClientError

logger = logging.getLogger(__name__)


class PuppetNotAvailableError(Exception):
    """Raised when Puppet returns 5xx / times out."""


@dataclass
class SearchResult:
    items: list[dict[str, Any]]
    took_ms: int
    source: str  # "puppet" | "sql_fallback"
    total: int


class SearchService:
    """Semantic search via Puppet with workspace isolation.

    Callers CANNOT supply the category — it is always derived from workspace_id.
    """

    def __init__(self, puppet_client: PuppetClient) -> None:
        self._puppet = puppet_client

    def _workspace_tag(self, workspace_id: UUID) -> str:
        return f"wm_{workspace_id}"

    async def search_work_items(
        self,
        *,
        workspace_id: UUID,
        query: str,
        limit: int = 20,
        additional_tags: list[str] | None = None,
    ) -> SearchResult:
        """Search work items via Puppet. Workspace tag is always enforced."""
        if not query or len(query.strip()) < 2:
            raise ValueError("query must be at least 2 characters")

        ws_tag = self._workspace_tag(workspace_id)
        tags = [ws_tag]
        # additional_tags are allowed for facet filters but MUST NOT override workspace
        if additional_tags:
            for t in additional_tags:
                if not t.startswith(ws_tag):
                    # Prefix with workspace tag for isolation
                    t = f"{ws_tag}:{t}"
                tags.append(t)

        start = time.monotonic()
        try:
            hits = await self._puppet.search(query.strip(), tags)
            took_ms = int((time.monotonic() - start) * 1000)

            if not hits:
                logger.info(
                    "search_work_items: Puppet returned 0 hits for query=%r ws=%s",
                    query,
                    workspace_id,
                )
            limited = hits[:limit]
            return SearchResult(
                items=limited,
                took_ms=took_ms,
                source="puppet",
                total=len(hits),
            )
        except PuppetClientError as exc:
            logger.warning(
                "search_work_items: PuppetClientError for ws=%s query=%r: %s",
                workspace_id,
                query,
                exc,
            )
            raise PuppetNotAvailableError(str(exc)) from exc
        except Exception as exc:
            logger.error(
                "search_work_items: unexpected error for ws=%s query=%r: %s",
                workspace_id,
                query,
                exc,
            )
            raise PuppetNotAvailableError(str(exc)) from exc
