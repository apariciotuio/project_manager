"""EP-06 — ReviewResponseService: submit responses to review requests.

Authorization: only the designated reviewer_id (for user reviews) can respond.
Decision=approved closes the request and calls ValidationService.on_review_closed() in the
same session (same transaction) to avoid split-brain.
Decision=rejected/changes_requested also closes the request and triggers FSM transition
to CHANGES_REQUESTED on the work item.

Events emitted:
- ReviewRespondedEvent (always, on success)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.application.events.event_bus import EventBus
from app.application.events.review_events import ReviewRespondedEvent
from app.application.services.review_request_service import (
    ReviewForbiddenError,
    ReviewNotFoundError,
    ReviewWithResponses,
)
from app.domain.models.review import (
    ContentRequiredError,
    ReviewAlreadyClosedError,
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
)
from app.domain.repositories.review_repository import (
    IReviewRequestRepository,
    IReviewResponseRepository,
)

logger = logging.getLogger(__name__)


class ReviewResponseService:
    def __init__(
        self,
        *,
        review_request_repo: IReviewRequestRepository,
        review_response_repo: IReviewResponseRepository,
        events: EventBus,
    ) -> None:
        self._requests = review_request_repo
        self._responses = review_response_repo
        self._events = events

    async def respond(
        self,
        *,
        request_id: UUID,
        responder_id: UUID,
        decision: ReviewDecision,
        content: str | None = None,
        workspace_id: UUID,
        validation_service: object | None = None,  # ValidationService — avoids circular import
    ) -> ReviewWithResponses:
        request = await self._requests.get(request_id)
        if request is None:
            raise ReviewNotFoundError(f"review request {request_id} not found")

        if request.status is not ReviewStatus.PENDING:
            raise ReviewAlreadyClosedError(
                f"review request {request_id} is not pending"
            )

        # Authorization: only designated reviewer can respond
        if request.reviewer_id is not None and request.reviewer_id != responder_id:
            raise ReviewForbiddenError("only the designated reviewer can respond")

        response = ReviewResponse.create(
            review_request_id=request_id,
            responder_id=responder_id,
            decision=decision,
            content=content,
        )
        await self._responses.create(response)

        # Close the request regardless of decision
        request.close()
        await self._requests.save(request)

        # Call ValidationService in the SAME transaction (no separate commit)
        if validation_service is not None and hasattr(validation_service, "on_review_closed"):
            try:
                await validation_service.on_review_closed(
                    review_request=request,
                    response=response,
                    workspace_id=workspace_id,
                )
            except Exception:
                logger.error(
                    "review_response.on_review_closed failed for request %s",
                    request_id,
                    exc_info=True,
                )
                raise  # re-raise to trigger rollback — atomicity is non-negotiable

        await self._events.emit(
            ReviewRespondedEvent(
                work_item_id=request.work_item_id,
                review_request_id=request.id,
                requester_id=request.requested_by,
                reviewer_id=request.reviewer_id,
                workspace_id=workspace_id,
                decision=decision.value,
                response_content=content,
            )
        )

        responses = await self._responses.list_for_request(request_id)
        return ReviewWithResponses(request=request, responses=responses)

    async def get_response(self, request_id: UUID) -> ReviewResponse | None:
        return await self._responses.get_for_request(request_id)
