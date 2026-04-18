"""EP-06 — ReviewRequest state machine + ReviewResponse validation + ValidationStatus."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.review import (
    ContentRequiredError,
    ReviewAlreadyClosedError,
    ReviewDecision,
    ReviewerType,
    ReviewInvariantError,
    ReviewRequest,
    ReviewResponse,
    ReviewStatus,
    ValidationState,
    ValidationStatus,
    ValidationTransitionError,
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


class TestReviewRequestInvariant:
    """Task 2.1 — reviewer target invariant."""

    def test_user_reviewer_valid(self) -> None:
        r = ReviewRequest.create_for_user(
            work_item_id=uuid4(),
            version_id=uuid4(),
            reviewer_id=uuid4(),
            requested_by=uuid4(),
        )
        assert r.reviewer_type is ReviewerType.USER
        assert r.reviewer_id is not None
        assert r.team_id is None

    def test_team_reviewer_valid(self) -> None:
        r = ReviewRequest.create_for_team(
            work_item_id=uuid4(),
            version_id=uuid4(),
            team_id=uuid4(),
            requested_by=uuid4(),
        )
        assert r.reviewer_type is ReviewerType.TEAM
        assert r.team_id is not None
        assert r.reviewer_id is None

    def test_user_type_missing_reviewer_id_raises(self) -> None:
        with pytest.raises(ReviewInvariantError):
            ReviewRequest(
                id=uuid4(),
                work_item_id=uuid4(),
                version_id=uuid4(),
                reviewer_type=ReviewerType.USER,
                reviewer_id=None,  # missing
                team_id=None,
                validation_rule_id=None,
                status=ReviewStatus.PENDING,
                requested_by=uuid4(),
                requested_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                cancelled_at=None,
            )

    def test_team_type_missing_team_id_raises(self) -> None:
        with pytest.raises(ReviewInvariantError):
            ReviewRequest(
                id=uuid4(),
                work_item_id=uuid4(),
                version_id=uuid4(),
                reviewer_type=ReviewerType.TEAM,
                reviewer_id=None,
                team_id=None,  # missing
                validation_rule_id=None,
                status=ReviewStatus.PENDING,
                requested_by=uuid4(),
                requested_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                cancelled_at=None,
            )

    def test_both_reviewer_and_team_raises(self) -> None:
        with pytest.raises(ReviewInvariantError):
            ReviewRequest(
                id=uuid4(),
                work_item_id=uuid4(),
                version_id=uuid4(),
                reviewer_type=ReviewerType.USER,
                reviewer_id=uuid4(),
                team_id=uuid4(),  # both set
                validation_rule_id=None,
                status=ReviewStatus.PENDING,
                requested_by=uuid4(),
                requested_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
                cancelled_at=None,
            )


class TestValidationStatus:
    """Tasks 2.5, 2.6 — ValidationStatus transition rules."""

    def _pending(self) -> ValidationStatus:
        return ValidationStatus.create_pending(work_item_id=uuid4(), rule_id="spec_review")

    def test_pending_to_passed_allowed(self) -> None:
        vs = self._pending()
        vs.mark_passed()
        assert vs.status is ValidationState.PASSED
        assert vs.passed_at is not None

    def test_pending_to_waived_allowed(self) -> None:
        vs = self._pending()
        vs.mark_waived(waived_by=uuid4())
        assert vs.status is ValidationState.WAIVED
        assert vs.waived_at is not None

    def test_pending_transition_to_obsolete_allowed(self) -> None:
        vs = self._pending()
        vs.transition_to(ValidationState.OBSOLETE)
        assert vs.status is ValidationState.OBSOLETE

    def test_passed_to_anything_blocked(self) -> None:
        vs = self._pending()
        vs.mark_passed()
        with pytest.raises(ValidationTransitionError):
            vs.transition_to(ValidationState.PENDING)

    def test_passed_to_waived_blocked(self) -> None:
        vs = self._pending()
        vs.mark_passed()
        with pytest.raises(ValidationTransitionError):
            vs.mark_waived(waived_by=uuid4())

    def test_mark_passed_idempotent(self) -> None:
        vs = self._pending()
        vs.mark_passed()
        passed_at_1 = vs.passed_at
        vs.mark_passed()  # second call — idempotent, no raise
        assert vs.passed_at == passed_at_1

    def test_waived_to_pending_blocked(self) -> None:
        vs = self._pending()
        vs.mark_waived(waived_by=uuid4())
        with pytest.raises(ValidationTransitionError):
            vs.transition_to(ValidationState.PENDING)

    def test_mark_passed_sets_review_request_id(self) -> None:
        vs = self._pending()
        rr_id = uuid4()
        vs.mark_passed(by_review_request_id=rr_id)
        assert vs.passed_by_review_request_id == rr_id
