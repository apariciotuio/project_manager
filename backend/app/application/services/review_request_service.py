"""EP-06 — ReviewRequestService: create, cancel, list review requests.

Authorization:
- Only the work item owner can create / cancel review requests.
- Reviewer cannot be the same as requester (SelfReviewForbiddenError).
- Listing is open to any workspace member.

Events emitted:
- ReviewRequestedEvent on creation
- ReviewDismissedEvent on cancellation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.application.events.event_bus import EventBus
from app.application.events.review_events import ReviewDismissedEvent, ReviewRequestedEvent
from app.domain.models.review import (
    ReviewAlreadyClosedError,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
)
from app.domain.repositories.review_repository import (
    IReviewRequestRepository,
    IReviewResponseRepository,
)

logger = logging.getLogger(__name__)


class ReviewNotFoundError(Exception):
    pass


class ReviewForbiddenError(Exception):
    pass


class SelfReviewForbiddenError(Exception):
    pass


class ValidationRuleNotFoundError(Exception):
    def __init__(self, rule_id: str) -> None:
        super().__init__(f"Validation rule {rule_id!r} not found")
        self.rule_id = rule_id


@dataclass
class ReviewWithResponses:
    request: ReviewRequest
    responses: list[ReviewResponse]


class ReviewRequestService:
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

    async def request_review(
        self,
        *,
        work_item_id: UUID,
        reviewer_id: UUID,
        version_id: UUID,
        requested_by: UUID,
        workspace_id: UUID,
        validation_rule_id: str | None = None,
    ) -> ReviewRequest:
        if reviewer_id == requested_by:
            raise SelfReviewForbiddenError("reviewer cannot be the same as requester")

        review = ReviewRequest.create_for_user(
            work_item_id=work_item_id,
            version_id=version_id,
            reviewer_id=reviewer_id,
            requested_by=requested_by,
            validation_rule_id=validation_rule_id,
        )
        saved = await self._requests.save(review)

        await self._events.emit(
            ReviewRequestedEvent(
                work_item_id=work_item_id,
                review_request_id=saved.id,
                requester_id=requested_by,
                reviewer_id=reviewer_id,
                workspace_id=workspace_id,
                reviewer_type="user",
            )
        )
        return saved

    async def cancel(
        self,
        *,
        request_id: UUID,
        actor_id: UUID,
        workspace_id: UUID,
    ) -> ReviewRequest:
        request = await self._requests.get(request_id)
        if request is None:
            raise ReviewNotFoundError(f"review request {request_id} not found")
        if request.requested_by != actor_id:
            raise ReviewForbiddenError("only the requester can cancel a review")
        request.cancel()
        saved = await self._requests.save(request)

        await self._events.emit(
            ReviewDismissedEvent(
                work_item_id=request.work_item_id,
                review_request_id=request.id,
                requester_id=request.requested_by,
                reviewer_id=request.reviewer_id,
                workspace_id=workspace_id,
            )
        )
        return saved

    async def list_for_work_item(
        self, work_item_id: UUID
    ) -> list[ReviewWithResponses]:
        requests = await self._requests.list_for_work_item(work_item_id)
        result: list[ReviewWithResponses] = []
        for req in requests:
            responses = await self._responses.list_for_request(req.id)
            result.append(ReviewWithResponses(request=req, responses=responses))
        return result

    async def list_pending_for_reviewer(self, user_id: UUID) -> list[ReviewRequest]:
        return await self._requests.list_pending_for_reviewer(user_id)

    async def get(self, request_id: UUID) -> ReviewRequest | None:
        return await self._requests.get(request_id)
