"""Dundun async callback controller — EP-03 Phase 3b.

Dundun POSTs agent results here after async invocation.
Authentication is HMAC-SHA256 over the raw request body using the shared
DUNDUN_CALLBACK_SECRET.  No JWT / no get_current_user.

POST /api/v1/dundun/callback
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.domain.models.gap_finding import GapSeverity, StoredGapFinding
from app.infrastructure.adapters.dundun_callback_verifier import verify_dundun_signature
from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
    AssistantSuggestionRepositoryImpl,
)
from app.infrastructure.persistence.gap_finding_repository_impl import (
    GapFindingRepositoryImpl,
)
from app.infrastructure.persistence.models.orm import WorkItemORM
from app.infrastructure.persistence.session_context import with_workspace
from app.presentation.dependencies import get_callback_session
from app.presentation.schemas.dundun_callback_schemas import DundunCallbackRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dundun"])

_SUGGESTION_EXPIRES_HOURS = 24

_INVALID_SIG_RESPONSE = JSONResponse(
    status_code=http_status.HTTP_401_UNAUTHORIZED,
    content={
        "error": {
            "code": "INVALID_SIGNATURE",
            "message": "invalid or missing signature",
            "details": {},
        }
    },
)


def _ok(agent: str, count: int, note: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={
            "data": {"processed": True, "agent": agent, "count": count},
            "message": note or "processed",
        },
    )


@router.post("/dundun/callback")
async def dundun_callback(
    request: Request,
    session: AsyncSession = Depends(get_callback_session),
) -> JSONResponse:
    # Build both repos off the same session so RLS SET LOCAL applies to both
    # and the two writes share one transaction.
    suggestion_repo = AssistantSuggestionRepositoryImpl(session)
    gap_repo = GapFindingRepositoryImpl(session)
    # 1. Read raw body — must happen before Pydantic parsing
    raw_body = await request.body()

    # 2. Verify HMAC signature
    header_sig = request.headers.get("X-Dundun-Signature", "")
    if not header_sig:
        return _INVALID_SIG_RESPONSE

    settings = get_settings()
    if not verify_dundun_signature(raw_body, header_sig, settings.dundun.callback_secret):
        return _INVALID_SIG_RESPONSE

    # 3. Parse body
    try:
        payload = DundunCallbackRequest.model_validate_json(raw_body)
    except Exception:
        return JSONResponse(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "invalid payload",
                    "details": {},
                }
            },
        )

    # 4. status=error — log and return 200, nothing persisted
    if payload.status == "error":
        logger.warning(
            "dundun_callback: agent=%s request_id=%s error=%s",
            payload.agent,
            payload.request_id,
            payload.error_message,
        )
        return _ok(payload.agent, 0, "error logged")

    # 5. Route by agent
    if payload.agent == "wm_suggestion_agent":
        return await _handle_suggestion(payload, session, suggestion_repo)

    if payload.agent == "wm_gap_agent":
        return await _handle_gap(payload, session, gap_repo)

    # wm_quick_action_agent — deferred to EP-04
    return JSONResponse(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": "quick_action callbacks are not yet implemented",
                "details": {},
            }
        },
    )


async def _resolve_workspace_id(session: AsyncSession, work_item_id: UUID) -> UUID:
    """Look up a work item's workspace_id and SET LOCAL for RLS.

    The Dundun callback runs outside user auth, so there's no workspace context
    from a JWT. We derive it from the referenced work item. Raises 422 if the
    work item does not exist.
    """
    stmt = select(WorkItemORM.workspace_id).where(WorkItemORM.id == work_item_id)
    workspace_id = (await session.execute(stmt)).scalar_one_or_none()
    if workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "WORK_ITEM_NOT_FOUND",
                    "message": f"work_item {work_item_id} not found",
                    "details": {},
                }
            },
        )
    await with_workspace(session, workspace_id)
    return workspace_id


async def _handle_suggestion(
    payload: DundunCallbackRequest,
    session: AsyncSession,
    repo: AssistantSuggestionRepositoryImpl,
) -> JSONResponse:
    """Persist suggestion rows for wm_suggestion_agent callbacks."""
    # Idempotency: already processed?
    existing = await repo.get_by_dundun_request_id(payload.request_id)
    if existing:
        logger.info(
            "dundun_callback: duplicate suggestion request_id=%s (already processed, %d rows)",
            payload.request_id,
            len(existing),
        )
        return _ok(payload.agent, len(existing), "duplicate request_id — already processed")

    items = payload.suggestions or []
    if not items:
        return _ok(payload.agent, 0, "no suggestions in payload")

    if payload.work_item_id is None or payload.user_id is None or payload.batch_id is None:
        logger.warning(
            "dundun_callback: suggestion missing required ids request_id=%s wi=%s batch=%s user=%s",
            payload.request_id,
            payload.work_item_id,
            payload.batch_id,
            payload.user_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id, batch_id and user_id are required for suggestions",
                    "details": {},
                }
            },
        )
    work_item_id: UUID = payload.work_item_id
    batch_id: UUID = payload.batch_id
    created_by: UUID = payload.user_id
    workspace_id = await _resolve_workspace_id(session, work_item_id)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=_SUGGESTION_EXPIRES_HOURS)

    suggestions = [
        AssistantSuggestion(
            id=uuid4(),
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            thread_id=None,
            section_id=item.section_id,
            proposed_content=item.proposed_content,
            current_content=item.current_content,
            rationale=item.rationale,
            status=SuggestionStatus.PENDING,
            version_number_target=1,  # TODO EP-07: fetch current version from work_item
            batch_id=batch_id,
            dundun_request_id=payload.request_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        for item in items
    ]

    persisted = await repo.create_batch(suggestions)
    logger.info(
        "dundun_callback: persisted %d suggestions for work_item=%s batch=%s request_id=%s",
        len(persisted),
        work_item_id,
        batch_id,
        payload.request_id,
    )
    return _ok(payload.agent, len(persisted))


async def _handle_gap(
    payload: DundunCallbackRequest,
    session: AsyncSession,
    repo: GapFindingRepositoryImpl,
) -> JSONResponse:
    """Persist gap findings for wm_gap_agent callbacks."""
    if payload.work_item_id is None:
        logger.warning(
            "dundun_callback: gap missing work_item_id request_id=%s",
            payload.request_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id is required for gap findings",
                    "details": {},
                }
            },
        )
    work_item_id: UUID = payload.work_item_id
    workspace_id = await _resolve_workspace_id(session, work_item_id)
    now = datetime.now(UTC)

    # Idempotency: check if this request_id was already processed
    existing = await repo.get_active_for_work_item(work_item_id, source="dundun")
    already_for_request = [f for f in existing if f.dundun_request_id == payload.request_id]
    if already_for_request:
        logger.info(
            "dundun_callback: duplicate gap request_id=%s (already processed, %d rows)",
            payload.request_id,
            len(already_for_request),
        )
        return _ok(
            payload.agent,
            len(already_for_request),
            "duplicate request_id — already processed",
        )

    # Invalidate previous Dundun findings for this work item before inserting fresh ones
    await repo.invalidate_for_work_item(work_item_id, now, source="dundun")

    raw_findings = payload.gap_findings or []
    if not raw_findings:
        return _ok(payload.agent, 0, "no gap findings in payload")

    findings = [
        StoredGapFinding(
            id=uuid4(),
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            dimension=f.dimension,
            severity=GapSeverity(f.severity),
            message=f.message,
            source="dundun",
            dundun_request_id=payload.request_id,
            created_at=now,
            invalidated_at=None,
        )
        for f in raw_findings
    ]

    persisted = await repo.insert_many(findings)
    logger.info(
        "dundun_callback: persisted %d gap findings for work_item=%s request_id=%s",
        len(persisted),
        work_item_id,
        payload.request_id,
    )
    return _ok(payload.agent, len(persisted))
