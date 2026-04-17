"""EP-09 — Search controller.

POST /api/v1/search  — Puppet-backed semantic search
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field

from app.application.services.search_service import PuppetNotAvailableError, SearchService
from app.presentation.dependencies import get_current_user, get_search_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


class SearchRequest(BaseModel):
    q: str = Field(min_length=2, max_length=500)
    limit: int = Field(default=20, ge=1, le=100)
    tags: list[str] | None = None  # additional facet tags


@router.post("/search")
async def search_work_items(
    body: SearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(get_search_service),
) -> dict[str, Any]:
    """Semantic search over work items via Puppet.

    workspace_id is always injected server-side — callers cannot override.
    Returns HTTP 503 if Puppet is unavailable (no SQL fallback — no FTS index exists).
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )

    try:
        result = await service.search_work_items(
            workspace_id=current_user.workspace_id,
            query=body.q,
            limit=body.limit,
            additional_tags=body.tags,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_QUERY", "message": str(exc), "details": {}}},
        ) from exc
    except PuppetNotAvailableError as exc:
        logger.error("search_work_items: Puppet unavailable: %s", exc)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "SEARCH_UNAVAILABLE",
                    "message": "search service unavailable",
                    "details": {},
                }
            },
        ) from exc

    return {
        "data": {
            "items": result.items,
            "took_ms": result.took_ms,
            "source": result.source,
            "total": result.total,
        },
        "message": "ok",
    }
