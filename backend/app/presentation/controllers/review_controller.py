"""EP-06 — Review controller.

Routes:
  POST   /api/v1/work-items/{id}/reviews          — request review
  POST   /api/v1/reviews/{id}/responses           — respond to review
  DELETE /api/v1/reviews/{id}                     — cancel
  GET    /api/v1/work-items/{id}/reviews          — list
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.review_service import (
    ReviewForbiddenError,
    ReviewNotFoundError,
    ReviewService,
    ReviewWithResponses,
)
from app.domain.models.review import (
    ContentRequiredError,
    ReviewAlreadyClosedError,
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
)
from app.presentation.dependencies import get_current_user, get_review_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reviews"])


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class RequestReviewBody(BaseModel):
    reviewer_id: UUID
    version_id: UUID
    validation_rule_id: str | None = None


class RespondReviewBody(BaseModel):
    decision: ReviewDecision
    content: str | None = None


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _review_request_payload(req: ReviewRequest) -> dict[str, Any]:
    return {
        "id": str(req.id),
        "work_item_id": str(req.work_item_id),
        "version_id": str(req.version_id),
        "reviewer_type": req.reviewer_type.value,
        "reviewer_id": str(req.reviewer_id) if req.reviewer_id else None,
        "team_id": str(req.team_id) if req.team_id else None,
        "validation_rule_id": req.validation_rule_id,
        "status": req.status.value,
        "requested_by": str(req.requested_by),
        "requested_at": req.requested_at.isoformat(),
        "cancelled_at": req.cancelled_at.isoformat() if req.cancelled_at else None,
    }


def _review_response_payload(resp: ReviewResponse) -> dict[str, Any]:
    return {
        "id": str(resp.id),
        "review_request_id": str(resp.review_request_id),
        "responder_id": str(resp.responder_id),
        "decision": resp.decision.value,
        "content": resp.content,
        "responded_at": resp.responded_at.isoformat(),
    }


def _review_with_responses_payload(rwr: ReviewWithResponses) -> dict[str, Any]:
    return {
        **_review_request_payload(rwr.request),
        "responses": [_review_response_payload(r) for r in rwr.responses],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/work-items/{work_item_id}/reviews", status_code=http_status.HTTP_201_CREATED)
async def request_review(
    work_item_id: UUID,
    body: RequestReviewBody,
    current_user: CurrentUser = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    review = await service.request_review(
        work_item_id=work_item_id,
        reviewer_id=body.reviewer_id,
        version_id=body.version_id,
        requested_by=current_user.id,
        validation_rule_id=body.validation_rule_id,
    )
    return _ok(_review_request_payload(review), "review requested")


@router.post("/reviews/{request_id}/responses", status_code=http_status.HTTP_201_CREATED)
async def respond_to_review(
    request_id: UUID,
    body: RespondReviewBody,
    current_user: CurrentUser = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        rwr = await service.respond(
            request_id=request_id,
            responder_id=current_user.id,
            decision=body.decision,
            content=body.content,
        )
    except ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ReviewAlreadyClosedError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {"code": "REVIEW_ALREADY_CLOSED", "message": str(exc), "details": {}}
            },
        ) from exc
    except ContentRequiredError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {"code": "CONTENT_REQUIRED", "message": str(exc), "details": {}}
            },
        ) from exc
    return _ok(_review_with_responses_payload(rwr), "response recorded")


@router.delete("/reviews/{request_id}", status_code=http_status.HTTP_200_OK)
async def cancel_review(
    request_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    try:
        review = await service.cancel(request_id=request_id, actor_id=current_user.id)
    except ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except ReviewAlreadyClosedError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {"code": "REVIEW_ALREADY_CLOSED", "message": str(exc), "details": {}}
            },
        ) from exc
    except ReviewForbiddenError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "FORBIDDEN", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_review_request_payload(review), "review cancelled")


@router.get("/work-items/{work_item_id}/reviews")
async def list_reviews(
    work_item_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: ReviewService = Depends(get_review_service),
) -> dict[str, Any]:
    _require_workspace(current_user)
    items = await service.list_for_work_item(work_item_id)
    return _ok([_review_with_responses_payload(r) for r in items])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_workspace(user: CurrentUser) -> None:
    if user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
