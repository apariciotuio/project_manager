"""EP-06 — ReviewService: request, respond, cancel, list."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.models.review import (
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


class ReviewNotFoundError(Exception):
    pass


class ReviewForbiddenError(Exception):
    pass


@dataclass
class ReviewWithResponses:
    request: ReviewRequest
    responses: list[ReviewResponse]


class ReviewService:
    def __init__(
        self,
        *,
        review_request_repo: IReviewRequestRepository,
        review_response_repo: IReviewResponseRepository,
    ) -> None:
        self._requests = review_request_repo
        self._responses = review_response_repo

    async def request_review(
        self,
        *,
        work_item_id: UUID,
        reviewer_id: UUID,
        version_id: UUID,
        requested_by: UUID,
        validation_rule_id: str | None = None,
    ) -> ReviewRequest:
        review = ReviewRequest.create_for_user(
            work_item_id=work_item_id,
            version_id=version_id,
            reviewer_id=reviewer_id,
            requested_by=requested_by,
            validation_rule_id=validation_rule_id,
        )
        return await self._requests.save(review)

    async def respond(
        self,
        *,
        request_id: UUID,
        responder_id: UUID,
        decision: ReviewDecision,
        content: str | None = None,
    ) -> ReviewWithResponses:
        request = await self._requests.get(request_id)
        if request is None:
            raise ReviewNotFoundError(f"review request {request_id} not found")

        if request.status is not ReviewStatus.PENDING:
            raise ReviewAlreadyClosedError(f"review request {request_id} is not pending")

        response = ReviewResponse.create(
            review_request_id=request_id,
            responder_id=responder_id,
            decision=decision,
            content=content,
        )
        await self._responses.create(response)

        if decision is ReviewDecision.APPROVED:
            request.close()
            await self._requests.save(request)

        responses = await self._responses.list_for_request(request_id)
        return ReviewWithResponses(request=request, responses=responses)

    async def cancel(self, *, request_id: UUID, actor_id: UUID) -> ReviewRequest:
        request = await self._requests.get(request_id)
        if request is None:
            raise ReviewNotFoundError(f"review request {request_id} not found")
        if request.requested_by != actor_id:
            raise ReviewForbiddenError("only the requester can cancel a review")
        request.cancel()
        return await self._requests.save(request)

    async def list_for_work_item(self, work_item_id: UUID) -> list[ReviewWithResponses]:
        requests = await self._requests.list_for_work_item(work_item_id)
        result: list[ReviewWithResponses] = []
        for req in requests:
            responses = await self._responses.list_for_request(req.id)
            result.append(ReviewWithResponses(request=req, responses=responses))
        return result
