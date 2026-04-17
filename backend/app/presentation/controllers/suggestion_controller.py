"""EP-03 Phase 7 — Suggestion controller.

Routes:
  POST  /api/v1/work-items/{id}/suggestion-sets  — enqueue suggestion generation (202)
  GET   /api/v1/work-items/{id}/suggestion-sets  — list pending+accepted batches
  GET   /api/v1/suggestion-sets/{batch_id}        — get batch + items
  PATCH /api/v1/suggestion-items/{item_id}        — accept/reject a single item
  POST  /api/v1/suggestion-sets/{batch_id}/apply  — apply accepted suggestions (EP-03 phase 3.7)
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from fastapi.responses import JSONResponse

from app.application.services.suggestion_service import SuggestionService
from app.presentation.dependencies import get_current_user, get_suggestion_service
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.schemas.suggestion_schemas import (
    GenerateSuggestionsRequest,
    PatchSuggestionStatusRequest,
    SuggestionBatchResponse,
    SuggestionItemResponse,
    parse_suggestion_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["suggestions"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail={"error": {"code": "FORBIDDEN", "message": "access denied", "details": {}}},
    )


def _not_found(resource: str = "suggestion") -> HTTPException:
    return HTTPException(
        status_code=http_status.HTTP_404_NOT_FOUND,
        detail={"error": {"code": "NOT_FOUND", "message": f"{resource} not found", "details": {}}},
    )


@router.post(
    "/work-items/{work_item_id}/suggestion-sets",
    status_code=http_status.HTTP_202_ACCEPTED,
)
async def generate_suggestions(
    work_item_id: UUID,
    body: GenerateSuggestionsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SuggestionService = Depends(get_suggestion_service),
) -> JSONResponse:
    """Dispatch Dundun wm_suggestion_agent asynchronously.

    Returns 202 with batch_id immediately. Suggestion rows are created when
    Dundun POSTs to the callback controller (Phase 3b).

    Note: Phase 6 Celery task wrapping is deferred. We call SuggestionService.generate
    directly here (sync path). Celery wrapping can be retrofitted without changing
    this handler's contract.
    """
    batch_id = await service.generate(
        work_item_id=work_item_id,
        user_id=current_user.id,
        thread_id=body.thread_id,
    )
    return JSONResponse(
        status_code=http_status.HTTP_202_ACCEPTED,
        content=_ok({"batch_id": str(batch_id)}, "suggestion generation dispatched"),
    )


@router.get("/work-items/{work_item_id}/suggestion-sets")
async def list_suggestion_sets(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
    service: SuggestionService = Depends(get_suggestion_service),
) -> dict[str, Any]:
    """List pending (non-expired) suggestions for a work item."""
    suggestions = await service.list_pending_for_work_item(work_item_id)
    return _ok([SuggestionItemResponse.from_domain(s).model_dump(mode="json") for s in suggestions])


@router.get("/suggestion-sets/{batch_id}")
async def get_suggestion_batch(
    batch_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
    service: SuggestionService = Depends(get_suggestion_service),
) -> dict[str, Any]:
    """Return all suggestion items in a batch."""
    suggestions = await service.list_for_batch(batch_id)
    if not suggestions:
        raise _not_found("suggestion batch")
    return _ok(SuggestionBatchResponse.from_suggestions(suggestions).model_dump(mode="json"))


@router.patch("/suggestion-items/{item_id}")
async def patch_suggestion_item(
    item_id: UUID,
    body: PatchSuggestionStatusRequest,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
    service: SuggestionService = Depends(get_suggestion_service),
) -> dict[str, Any]:
    """Accept or reject a single suggestion item."""
    try:
        new_status = parse_suggestion_status(body.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc

    try:
        updated = await service.update_single_status(item_id, new_status)
    except ValueError as exc:
        raise _not_found() from exc

    return _ok(SuggestionItemResponse.from_domain(updated).model_dump(mode="json"))


@router.post("/suggestion-sets/{batch_id}/apply", status_code=http_status.HTTP_200_OK)
async def apply_suggestion_batch(
    batch_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: SuggestionService = Depends(get_suggestion_service),
) -> dict[str, Any]:
    """Apply all accepted suggestions in the batch to their target sections.

    Idempotent: already-applied suggestions are skipped.

    Returns applied_count, skipped_count, and latest_version_id (if available).

    404 — batch not found
    422 — batch exists but has no accepted suggestions to apply
    """
    try:
        result = await service.apply_accepted_batch(batch_id=batch_id, actor_id=current_user.id)
    except LookupError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "NO_ACCEPTED_SUGGESTIONS", "message": str(exc), "details": {}}},
        ) from exc

    latest = result["latest_version"]
    return _ok(
        {
            "applied_count": result["applied_count"],
            "skipped_count": result["skipped_count"],
            "latest_version_id": str(latest.id) if latest is not None else None,
            "latest_version_number": latest.version_number if latest is not None else None,
        },
        "batch applied",
    )
