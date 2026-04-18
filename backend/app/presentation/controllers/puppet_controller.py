"""EP-13 — Puppet REST endpoints.

Three endpoint groups:

1. POST /puppet/ingest-callback
   HMAC-only (no user context) — Puppet notifies us when async ingestion completes.

2. POST /puppet/search
   Authenticated + workspace-scoped search proxy.

3. GET  /puppet/ingest-requests
   POST /puppet/ingest-requests/{id}/retry
   Admin observability endpoints (workspace-scoped).
"""
from __future__ import annotations

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infrastructure.adapters.puppet_callback_verifier import verify_puppet_signature
from app.infrastructure.pagination import InvalidCursorError, PaginationCursor
from app.presentation.dependencies import (
    CurrentUser,
    get_callback_session,
    get_current_user,
    get_scoped_session,
)
from app.presentation.schemas.puppet_schemas import (
    PuppetCallbackRequest,
    PuppetIngestRequestResponse,
    PuppetSearchRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["puppet"])

_INVALID_SIG = JSONResponse(
    status_code=http_status.HTTP_401_UNAUTHORIZED,
    content={
        "error": {
            "code": "INVALID_SIGNATURE",
            "message": "invalid or missing Puppet signature",
            "details": {},
        }
    },
)


# ---------------------------------------------------------------------------
# POST /puppet/ingest-callback — HMAC-only
# ---------------------------------------------------------------------------


@router.post("/puppet/ingest-callback")
async def puppet_ingest_callback(
    request: Request,
    session: AsyncSession = Depends(get_callback_session),
) -> JSONResponse:
    """Receive async ingestion result from Puppet.

    Authentication: HMAC-SHA256 over raw body in X-Puppet-Signature header.
    Idempotent by ingest_request_id — duplicate calls return 200 without state change.
    """
    raw_body = await request.body()
    header_sig = request.headers.get("X-Puppet-Signature", "")
    settings = get_settings()

    if not verify_puppet_signature(raw_body, header_sig, settings.puppet.callback_secret):
        return _INVALID_SIG

    try:
        body_dict = json.loads(raw_body)
        payload = PuppetCallbackRequest(**body_dict)
    except Exception as exc:
        logger.warning("puppet_ingest_callback: invalid body: %s", exc)
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        )

    from app.infrastructure.persistence.puppet_ingest_request_repository_impl import (
        PuppetIngestRequestRepositoryImpl,
    )

    repo = PuppetIngestRequestRepositoryImpl(session)
    req = await repo.get(payload.ingest_request_id)

    if req is None:
        return JSONResponse(
            status_code=http_status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"ingest_request {payload.ingest_request_id} not found",
                    "details": {},
                }
            },
        )

    # Idempotent: if already terminal, return 200 without mutation
    if req.status in ("succeeded", "skipped"):
        return JSONResponse(
            status_code=http_status.HTTP_200_OK,
            content={"data": {"processed": False}, "message": "already processed"},
        )

    if payload.status == "succeeded" and payload.puppet_doc_id:
        req.mark_succeeded(payload.puppet_doc_id)
    elif payload.status == "failed":
        req.mark_failed(payload.error or "Puppet reported failure")
    else:
        return JSONResponse(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"unexpected status={payload.status!r}",
                    "details": {},
                }
            },
        )

    await repo.save(req)
    await session.commit()

    logger.info(
        "puppet_ingest_callback: id=%s status=%s doc_id=%s",
        req.id,
        req.status,
        req.puppet_doc_id,
    )

    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={"data": {"processed": True, "status": req.status}, "message": "ok"},
    )


# ---------------------------------------------------------------------------
# POST /puppet/search — authenticated + workspace-scoped
# ---------------------------------------------------------------------------


@router.post("/puppet/search")
async def puppet_search(
    body: PuppetSearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> JSONResponse:
    """Proxy search to Puppet — workspace_id always injected server-side."""
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )

    settings = get_settings()

    if settings.puppet.use_fake:
        from tests.fakes.fake_puppet_client import FakePuppetClient
        puppet_client = FakePuppetClient()
    else:
        from app.infrastructure.adapters.puppet_http_client import PuppetHTTPClient
        puppet_client = PuppetHTTPClient(
            base_url=settings.puppet.base_url,
            api_key=settings.puppet.api_key,
        )

    # Category is always derived from workspace — never from client input
    category = f"wm_{current_user.workspace_id}"
    tags = [category]
    if body.category:
        # Additional client-supplied category allowed only within the workspace namespace
        # Ensure it still has the workspace prefix for isolation
        safe_cat = body.category if body.category.startswith(category) else f"{category}_{body.category}"
        tags.append(safe_cat)

    try:
        from app.domain.ports.puppet import PuppetClientError
        hits = await puppet_client.search(body.query, tags)
    except Exception as exc:
        logger.error("puppet_search: Puppet unavailable: %s", exc)
        return JSONResponse(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "SEARCH_UNAVAILABLE",
                    "message": "Puppet search service unavailable",
                    "details": {},
                }
            },
        )

    limited = hits[: body.limit]
    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={"data": limited, "message": "ok"},
    )


# ---------------------------------------------------------------------------
# GET /puppet/ingest-requests — admin observability
# ---------------------------------------------------------------------------


@router.get("/puppet/ingest-requests")
async def list_ingest_requests(
    status: str | None = None,
    cursor: str | None = Query(default=None),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> JSONResponse:
    """List ingest requests for the current workspace — cursor-paginated.

    Keyset order: (created_at DESC, id DESC).
    Response shape: { data: { items: [...], pagination: { next_cursor, has_more } } }
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )

    decoded_cursor: PaginationCursor | None = None
    if cursor is not None:
        try:
            decoded_cursor = PaginationCursor.decode(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CURSOR", "message": str(exc), "details": {}}},
            ) from exc

    from app.infrastructure.persistence.puppet_ingest_request_repository_impl import (
        PuppetIngestRequestRepositoryImpl,
    )

    repo = PuppetIngestRequestRepositoryImpl(session)
    result = await repo.list_by_workspace_cursor(
        workspace_id=current_user.workspace_id,
        status=status,
        cursor=decoded_cursor,
        page_size=page_size,
    )

    items = [
        {
            "id": str(r.id),
            "workspace_id": str(r.workspace_id),
            "source_kind": r.source_kind,
            "work_item_id": str(r.work_item_id) if r.work_item_id else None,
            "status": r.status,
            "puppet_doc_id": r.puppet_doc_id,
            "attempts": r.attempts,
            "last_error": r.last_error,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
            "succeeded_at": r.succeeded_at.isoformat() if r.succeeded_at else None,
        }
        for r in result.rows
    ]

    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={
            "data": {
                "items": items,
                "pagination": {
                    "next_cursor": result.next_cursor,
                    "has_more": result.has_next,
                },
            },
            "message": "ok",
        },
    )


# ---------------------------------------------------------------------------
# POST /puppet/ingest-requests/{id}/retry — admin manual retry
# ---------------------------------------------------------------------------


@router.post("/puppet/ingest-requests/{request_id}/retry")
async def retry_ingest_request(
    request_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> JSONResponse:
    """Reset a failed ingest request to queued (attempts=0) for manual retry."""
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace in token", "details": {}}},
        )

    from app.infrastructure.persistence.puppet_ingest_request_repository_impl import (
        PuppetIngestRequestRepositoryImpl,
    )

    repo = PuppetIngestRequestRepositoryImpl(session)
    req = await repo.get(request_id)

    if req is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "ingest request not found", "details": {}}},
        )

    # Workspace isolation — the RLS handles reads but we enforce explicitly for writes
    if req.workspace_id != current_user.workspace_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "ingest request not found", "details": {}}},
        )

    if req.status not in ("failed", "skipped"):
        return JSONResponse(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "INVALID_INPUT",
                    "message": f"cannot retry request in status={req.status!r}",
                    "details": {},
                }
            },
        )

    req.reset_for_retry()
    await repo.save(req)
    await session.commit()

    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={"data": {"id": str(req.id), "status": req.status}, "message": "queued for retry"},
    )
