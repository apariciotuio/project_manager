"""Unit tests for ValidationService — EP-06.

Tasks: 4.15 (get_checklist), 4.16 (on_review_closed), 4.17 (waive_validation).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.events.event_bus import EventBus
from app.application.services.validation_service import ValidationService
from app.domain.models.review import (
    ReviewDecision,
    ReviewRequest,
    ReviewResponse,
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
    WaiveRequiredRuleError,
)
from tests.fakes.fake_review_repositories import (
    FakeReviewRequestRepository,
    FakeValidationRequirementRepository,
    FakeValidationStatusRepository,
)


class FakeEventBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[object] = []

    async def emit(self, event: object) -> None:
        self.emitted.append(event)


def _rule(rule_id: str, *, required: bool = True) -> ValidationRequirement:
    return ValidationRequirement(
        rule_id=rule_id,
        label=rule_id.title(),
        required=required,
        applies_to=(),
    )


def _make_svc(
    req_repo: FakeValidationRequirementRepository | None = None,
    status_repo: FakeValidationStatusRepository | None = None,
    review_request_repo: FakeReviewRequestRepository | None = None,
    bus: FakeEventBus | None = None,
) -> ValidationService:
    return ValidationService(
        requirement_repo=req_repo or FakeValidationRequirementRepository(),
        status_repo=status_repo or FakeValidationStatusRepository(),
        review_request_repo=review_request_repo or FakeReviewRequestRepository(),
        events=bus or FakeEventBus(),
    )


class TestGetChecklist:
    @pytest.mark.asyncio
    async def test_splits_required_recommended(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review", required=True))
        req_repo.seed(_rule("tech_review", required=False))
        svc = _make_svc(req_repo=req_repo)

        result = await svc.get_checklist(uuid4(), uuid4(), "story")

        required_ids = [r.rule_id for r, _ in result.required]
        recommended_ids = [r.rule_id for r, _ in result.recommended]
        assert "spec_review" in required_ids
        assert "tech_review" in recommended_ids

    @pytest.mark.asyncio
    async def test_includes_current_status(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review", required=True))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id="spec_review")
        vs.mark_passed()
        await status_repo.save(vs)

        svc = _make_svc(req_repo=req_repo, status_repo=status_repo)
        result = await svc.get_checklist(work_item_id, uuid4(), "story")

        _, status = result.required[0]
        assert status is not None
        assert status.status is ValidationState.PASSED


class TestOnReviewClosed:
    @pytest.mark.asyncio
    async def test_approved_with_linked_rule_marks_passed(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id="spec_review")
        await status_repo.save(vs)

        rr_id = uuid4()
        review_req = ReviewRequest.create_for_user(
            work_item_id=work_item_id,
            version_id=uuid4(),
            reviewer_id=uuid4(),
            requested_by=uuid4(),
            validation_rule_id="spec_review",
        )
        review_req.id = rr_id
        response = ReviewResponse.create(
            review_request_id=rr_id,
            responder_id=uuid4(),
            decision=ReviewDecision.APPROVED,
        )

        svc = _make_svc(req_repo=req_repo, status_repo=status_repo)
        await svc.on_review_closed(review_req, response, uuid4())

        updated = await status_repo.get_by_work_item_and_rule(work_item_id, "spec_review")
        assert updated is not None
        assert updated.status is ValidationState.PASSED
        assert updated.passed_by_review_request_id == rr_id

    @pytest.mark.asyncio
    async def test_rejected_does_not_change_status(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id="spec_review")
        await status_repo.save(vs)

        review_req = ReviewRequest.create_for_user(
            work_item_id=work_item_id,
            version_id=uuid4(),
            reviewer_id=uuid4(),
            requested_by=uuid4(),
            validation_rule_id="spec_review",
        )
        response = ReviewResponse.create(
            review_request_id=review_req.id,
            responder_id=uuid4(),
            decision=ReviewDecision.REJECTED,
            content="needs rework",
        )

        svc = _make_svc(req_repo=req_repo, status_repo=status_repo)
        await svc.on_review_closed(review_req, response, uuid4())

        updated = await status_repo.get_by_work_item_and_rule(work_item_id, "spec_review")
        assert updated is not None
        assert updated.status is ValidationState.PENDING

    @pytest.mark.asyncio
    async def test_no_linked_rule_is_noop(self) -> None:
        status_repo = FakeValidationStatusRepository()
        review_req = ReviewRequest.create_for_user(
            work_item_id=uuid4(),
            version_id=uuid4(),
            reviewer_id=uuid4(),
            requested_by=uuid4(),
            validation_rule_id=None,  # no linked rule
        )
        response = ReviewResponse.create(
            review_request_id=review_req.id,
            responder_id=uuid4(),
            decision=ReviewDecision.APPROVED,
        )

        svc = _make_svc(status_repo=status_repo)
        await svc.on_review_closed(review_req, response, uuid4())
        # Nothing changed — no status rows created
        assert len(status_repo._store) == 0

    @pytest.mark.asyncio
    async def test_already_passed_is_idempotent(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id="spec_review")
        vs.mark_passed(by_review_request_id=uuid4())
        first_passed_at = vs.passed_at
        await status_repo.save(vs)

        review_req = ReviewRequest.create_for_user(
            work_item_id=work_item_id,
            version_id=uuid4(),
            reviewer_id=uuid4(),
            requested_by=uuid4(),
            validation_rule_id="spec_review",
        )
        response = ReviewResponse.create(
            review_request_id=review_req.id,
            responder_id=uuid4(),
            decision=ReviewDecision.APPROVED,
        )

        svc = _make_svc(req_repo=req_repo, status_repo=status_repo)
        await svc.on_review_closed(review_req, response, uuid4())  # second call

        updated = await status_repo.get_by_work_item_and_rule(work_item_id, "spec_review")
        assert updated is not None
        assert updated.passed_at == first_passed_at  # timestamp unchanged


class TestWaiveValidation:
    @pytest.mark.asyncio
    async def test_recommended_rule_can_be_waived(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("tech_review", required=False))
        work_item_id = uuid4()
        actor_id = uuid4()
        svc = _make_svc(req_repo=req_repo)

        vs = await svc.waive_validation(
            work_item_id=work_item_id,
            rule_id="tech_review",
            workspace_id=uuid4(),
            waived_by=actor_id,
        )
        assert vs.status is ValidationState.WAIVED
        assert vs.waived_by == actor_id

    @pytest.mark.asyncio
    async def test_required_rule_cannot_be_waived(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_rule("spec_review", required=True))
        svc = _make_svc(req_repo=req_repo)

        with pytest.raises(WaiveRequiredRuleError):
            await svc.waive_validation(
                work_item_id=uuid4(),
                rule_id="spec_review",
                workspace_id=uuid4(),
                waived_by=uuid4(),
            )
