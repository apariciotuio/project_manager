"""Unit tests for ReviewRequestService — EP-06.

Tasks: 4.1 (create user), 4.3 (non-owner forbidden via SelfReviewForbiddenError),
       4.4 (cancel), 4.5 (list).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.events.event_bus import EventBus
from app.application.events.review_events import ReviewDismissedEvent, ReviewRequestedEvent
from app.application.services.review_request_service import (
    ReviewForbiddenError,
    ReviewNotFoundError,
    ReviewRequestService,
    SelfReviewForbiddenError,
)
from app.domain.models.review import ReviewAlreadyClosedError, ReviewStatus
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


def _make_svc(
    request_repo: FakeReviewRequestRepository | None = None,
    response_repo: FakeReviewResponseRepository | None = None,
    bus: FakeEventBus | None = None,
) -> tuple[ReviewRequestService, FakeEventBus]:
    bus = bus or FakeEventBus()
    svc = ReviewRequestService(
        review_request_repo=request_repo or FakeReviewRequestRepository(),
        review_response_repo=response_repo or FakeReviewResponseRepository(),
        events=bus,
    )
    return svc, bus


class TestRequestReview:
    @pytest.mark.asyncio
    async def test_creates_pending_request(self) -> None:
        svc, bus = _make_svc()
        work_item_id = uuid4()
        reviewer_id = uuid4()
        requester_id = uuid4()
        workspace_id = uuid4()

        req = await svc.request_review(
            work_item_id=work_item_id,
            reviewer_id=reviewer_id,
            version_id=uuid4(),
            requested_by=requester_id,
            workspace_id=workspace_id,
        )

        assert req.status is ReviewStatus.PENDING
        assert req.reviewer_id == reviewer_id
        assert req.requested_by == requester_id
        assert req.work_item_id == work_item_id

    @pytest.mark.asyncio
    async def test_emits_review_requested_event(self) -> None:
        svc, bus = _make_svc()
        workspace_id = uuid4()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=uuid4(),
            requested_by=uuid4(),
            workspace_id=workspace_id,
        )

        assert len(bus.emitted) == 1
        event = bus.emitted[0]
        assert isinstance(event, ReviewRequestedEvent)
        assert event.workspace_id == workspace_id
        assert event.review_request_id == req.id

    @pytest.mark.asyncio
    async def test_self_review_forbidden(self) -> None:
        svc, _ = _make_svc()
        actor = uuid4()
        with pytest.raises(SelfReviewForbiddenError):
            await svc.request_review(
                work_item_id=uuid4(),
                reviewer_id=actor,
                version_id=uuid4(),
                requested_by=actor,  # same as reviewer
                workspace_id=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_pins_version_id(self) -> None:
        svc, _ = _make_svc()
        version_id = uuid4()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=version_id,
            requested_by=uuid4(),
            workspace_id=uuid4(),
        )
        assert req.version_id == version_id


class TestCancelReview:
    @pytest.mark.asyncio
    async def test_owner_can_cancel_pending(self) -> None:
        svc, bus = _make_svc()
        requester_id = uuid4()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=uuid4(),
            requested_by=requester_id,
            workspace_id=uuid4(),
        )

        cancelled = await svc.cancel(
            request_id=req.id,
            actor_id=requester_id,
            workspace_id=uuid4(),
        )
        assert cancelled.status is ReviewStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_emits_dismissed_event(self) -> None:
        svc, bus = _make_svc()
        requester_id = uuid4()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=uuid4(),
            requested_by=requester_id,
            workspace_id=uuid4(),
        )
        bus.emitted.clear()

        await svc.cancel(request_id=req.id, actor_id=requester_id, workspace_id=uuid4())
        assert any(isinstance(e, ReviewDismissedEvent) for e in bus.emitted)

    @pytest.mark.asyncio
    async def test_non_owner_cannot_cancel(self) -> None:
        svc, _ = _make_svc()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=uuid4(),
            requested_by=uuid4(),
            workspace_id=uuid4(),
        )
        with pytest.raises(ReviewForbiddenError):
            await svc.cancel(request_id=req.id, actor_id=uuid4(), workspace_id=uuid4())

    @pytest.mark.asyncio
    async def test_cancel_not_found_raises(self) -> None:
        svc, _ = _make_svc()
        with pytest.raises(ReviewNotFoundError):
            await svc.cancel(request_id=uuid4(), actor_id=uuid4(), workspace_id=uuid4())

    @pytest.mark.asyncio
    async def test_cancel_closed_request_raises(self) -> None:
        svc, _ = _make_svc()
        requester_id = uuid4()
        req = await svc.request_review(
            work_item_id=uuid4(),
            reviewer_id=uuid4(),
            version_id=uuid4(),
            requested_by=requester_id,
            workspace_id=uuid4(),
        )
        # Cancel once
        await svc.cancel(request_id=req.id, actor_id=requester_id, workspace_id=uuid4())
        # Cancel again — should raise
        with pytest.raises(ReviewAlreadyClosedError):
            await svc.cancel(request_id=req.id, actor_id=requester_id, workspace_id=uuid4())
