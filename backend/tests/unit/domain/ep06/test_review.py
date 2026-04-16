"""EP-06 — ReviewRequest state machine + ReviewResponse validation."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.review import (
    ContentRequiredError,
    ReviewAlreadyClosedError,
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
)


def _request() -> ReviewRequest:
    return ReviewRequest.create_for_user(
        work_item_id=uuid4(),
        version_id=uuid4(),
        reviewer_id=uuid4(),
        requested_by=uuid4(),
    )


class TestReviewRequest:
    def test_created_pending(self) -> None:
        r = _request()
        assert r.status is ReviewStatus.PENDING
        assert r.cancelled_at is None

    def test_cancel_sets_timestamp(self) -> None:
        r = _request()
        r.cancel()
        assert r.status is ReviewStatus.CANCELLED
        assert r.cancelled_at is not None

    def test_cannot_cancel_twice(self) -> None:
        r = _request()
        r.cancel()
        with pytest.raises(ReviewAlreadyClosedError):
            r.cancel()

    def test_cannot_close_cancelled(self) -> None:
        r = _request()
        r.cancel()
        with pytest.raises(ReviewAlreadyClosedError):
            r.close()

    def test_close_sets_status(self) -> None:
        r = _request()
        r.close()
        assert r.status is ReviewStatus.CLOSED


class TestReviewResponse:
    def test_approved_no_content_ok(self) -> None:
        resp = ReviewResponse.create(
            review_request_id=uuid4(),
            responder_id=uuid4(),
            decision=ReviewDecision.APPROVED,
        )
        assert resp.decision is ReviewDecision.APPROVED

    def test_rejected_without_content_raises(self) -> None:
        with pytest.raises(ContentRequiredError):
            ReviewResponse.create(
                review_request_id=uuid4(),
                responder_id=uuid4(),
                decision=ReviewDecision.REJECTED,
                content=None,
            )

    def test_changes_requested_requires_content(self) -> None:
        with pytest.raises(ContentRequiredError):
            ReviewResponse.create(
                review_request_id=uuid4(),
                responder_id=uuid4(),
                decision=ReviewDecision.CHANGES_REQUESTED,
                content="   ",
            )

    def test_rejected_with_content_ok(self) -> None:
        resp = ReviewResponse.create(
            review_request_id=uuid4(),
            responder_id=uuid4(),
            decision=ReviewDecision.REJECTED,
            content="needs work",
        )
        assert resp.content == "needs work"
