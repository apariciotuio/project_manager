"""Unit tests for ReviewResponseService — EP-06.

Tasks: 4.6 (approved closes + calls validation), 4.7 (rejected),
       4.8 (changes_requested), 4.9 (non-assigned forbidden), 4.11 (already closed),
       4.12 (approved without content succeeds).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.events.event_bus import EventBus
from app.application.events.review_events import ReviewRespondedEvent
from app.application.services.review_request_service import ReviewForbiddenError, ReviewNotFoundError
from app.application.services.review_response_service import ReviewResponseService
from app.domain.models.review import (
    ContentRequiredError,
    ReviewAlreadyClosedError,
    ReviewDecision,
    ReviewRequest,
    ReviewStatus,
)
from tests.fakes.fake_review_repositories import (
    FakeReviewRequestRepository,
    FakeReviewResponseRepository,
)


class FakeEventBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[object] = []

    async def emit(self, event: object) -> None:
        self.emitted.append(event)


def _pending_request(
    reviewer_id: uuid4 | None = None,
) -> ReviewRequest:
    rid = reviewer_id or uuid4()
    return ReviewRequest.create_for_user(
        work_item_id=uuid4(),
        version_id=uuid4(),
        reviewer_id=rid,
        requested_by=uuid4(),
    )


def _make_svc(
    request_repo: FakeReviewRequestRepository | None = None,
    response_repo: FakeReviewResponseRepository | None = None,
    bus: FakeEventBus | None = None,
) -> tuple[ReviewResponseService, FakeEventBus]:
    bus = bus or FakeEventBus()
    svc = ReviewResponseService(
        review_request_repo=request_repo or FakeReviewRequestRepository(),
        review_response_repo=response_repo or FakeReviewResponseRepository(),
        events=bus,
    )
    return svc, bus


class TestRespondApproved:
    @pytest.mark.asyncio
    async def test_approved_closes_request(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        rwr = await svc.respond(
            request_id=req.id,
            responder_id=reviewer_id,
            decision=ReviewDecision.APPROVED,
            workspace_id=uuid4(),
        )

        assert rwr.request.status is ReviewStatus.CLOSED

    @pytest.mark.asyncio
    async def test_approved_without_content_succeeds(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        rwr = await svc.respond(
            request_id=req.id,
            responder_id=reviewer_id,
            decision=ReviewDecision.APPROVED,
            content=None,
            workspace_id=uuid4(),
        )
        assert rwr.responses[0].content is None

    @pytest.mark.asyncio
    async def test_approved_emits_responded_event(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, bus = _make_svc(request_repo=req_repo)
        await svc.respond(
            request_id=req.id,
            responder_id=reviewer_id,
            decision=ReviewDecision.APPROVED,
            workspace_id=uuid4(),
        )
        assert any(isinstance(e, ReviewRespondedEvent) for e in bus.emitted)


class TestRespondRejected:
    @pytest.mark.asyncio
    async def test_rejected_requires_content(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        with pytest.raises(ContentRequiredError):
            await svc.respond(
                request_id=req.id,
                responder_id=reviewer_id,
                decision=ReviewDecision.REJECTED,
                content=None,
                workspace_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_rejected_with_content_closes_request(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        rwr = await svc.respond(
            request_id=req.id,
            responder_id=reviewer_id,
            decision=ReviewDecision.REJECTED,
            content="This needs rework",
            workspace_id=uuid4(),
        )
        assert rwr.request.status is ReviewStatus.CLOSED

    @pytest.mark.asyncio
    async def test_changes_requested_requires_content(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        with pytest.raises(ContentRequiredError):
            await svc.respond(
                request_id=req.id,
                responder_id=reviewer_id,
                decision=ReviewDecision.CHANGES_REQUESTED,
                content="   ",
                workspace_id=uuid4(),
            )


class TestRespondAuthorization:
    @pytest.mark.asyncio
    async def test_non_assigned_reviewer_raises(self) -> None:
        req_repo = FakeReviewRequestRepository()
        req = _pending_request()
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        with pytest.raises(ReviewForbiddenError):
            await svc.respond(
                request_id=req.id,
                responder_id=uuid4(),  # different from reviewer_id
                decision=ReviewDecision.APPROVED,
                workspace_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_not_found_raises(self) -> None:
        svc, _ = _make_svc()
        with pytest.raises(ReviewNotFoundError):
            await svc.respond(
                request_id=uuid4(),
                responder_id=uuid4(),
                decision=ReviewDecision.APPROVED,
                workspace_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_already_closed_raises(self) -> None:
        req_repo = FakeReviewRequestRepository()
        reviewer_id = uuid4()
        req = _pending_request(reviewer_id=reviewer_id)
        await req_repo.save(req)

        svc, _ = _make_svc(request_repo=req_repo)
        # First response
        await svc.respond(
            request_id=req.id,
            responder_id=reviewer_id,
            decision=ReviewDecision.APPROVED,
            workspace_id=uuid4(),
        )
        # Second attempt on same request
        with pytest.raises(ReviewAlreadyClosedError):
            await svc.respond(
                request_id=req.id,
                responder_id=reviewer_id,
                decision=ReviewDecision.APPROVED,
                workspace_id=uuid4(),
            )
