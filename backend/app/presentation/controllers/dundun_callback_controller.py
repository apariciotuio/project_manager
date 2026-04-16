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

from fastapi import APIRouter, Depends, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse

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
from app.presentation.dependencies import get_assistant_suggestion_repo, get_gap_finding_repo
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
    suggestion_repo: AssistantSuggestionRepositoryImpl = Depends(get_assistant_suggestion_repo),
    gap_repo: GapFindingRepositoryImpl = Depends(get_gap_finding_repo),
) -> JSONResponse:
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
        return await _handle_suggestion(payload, suggestion_repo)

    if payload.agent == "wm_gap_agent":
        return await _handle_gap(payload, gap_repo)

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


async def _handle_suggestion(
    payload: DundunCallbackRequest,
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

    work_item_id: UUID = payload.work_item_id or uuid4()  # fallback — should always be set
    batch_id: UUID = payload.batch_id or uuid4()
    created_by: UUID = payload.user_id or uuid4()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=_SUGGESTION_EXPIRES_HOURS)

    suggestions = [
        AssistantSuggestion(
            id=uuid4(),
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
    repo: GapFindingRepositoryImpl,
) -> JSONResponse:
    """Persist gap findings for wm_gap_agent callbacks."""
    work_item_id: UUID = payload.work_item_id or uuid4()
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
