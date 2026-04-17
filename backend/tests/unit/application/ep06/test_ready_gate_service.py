"""Unit tests for ReadyGateService — EP-06.

Tasks: 4.20 (all passed → ok), (one pending → blocked), (only recommended pending → ok),
       4.20a (required+waived → blocked with warning).
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.ready_gate_service import GateResult, ReadyGateService
from app.domain.models.review import (
    ValidationRequirement,
    ValidationState,
    ValidationStatus,
)
from tests.fakes.fake_review_repositories import (
    FakeValidationRequirementRepository,
    FakeValidationStatusRepository,
)


def _req(rule_id: str, *, required: bool = True) -> ValidationRequirement:
    return ValidationRequirement(
        rule_id=rule_id,
        label=rule_id.replace("_", " ").title(),
        required=required,
        applies_to=(),
    )


def _vs(work_item_id: uuid4, rule_id: str, status: ValidationState) -> ValidationStatus:
    vs = ValidationStatus.create_pending(work_item_id=work_item_id, rule_id=rule_id)
    if status is ValidationState.PASSED:
        vs.mark_passed()
    elif status is ValidationState.WAIVED:
        vs.mark_waived(waived_by=uuid4())
    elif status is ValidationState.OBSOLETE:
        vs.transition_to(ValidationState.OBSOLETE)
    return vs


def _make_svc(
    req_repo: FakeValidationRequirementRepository,
    status_repo: FakeValidationStatusRepository,
) -> ReadyGateService:
    return ReadyGateService(requirement_repo=req_repo, status_repo=status_repo)


class TestReadyGate:
    @pytest.mark.asyncio
    async def test_no_rules_gate_passes(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        status_repo = FakeValidationStatusRepository()
        svc = _make_svc(req_repo, status_repo)

        result = await svc.check(uuid4(), uuid4(), "story")
        assert result.ok is True
        assert result.blockers == []

    @pytest.mark.asyncio
    async def test_all_required_passed_gate_passes(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_req("spec_review"))
        req_repo.seed(_req("tech_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        await status_repo.save(_vs(work_item_id, "spec_review", ValidationState.PASSED))
        await status_repo.save(_vs(work_item_id, "tech_review", ValidationState.PASSED))

        svc = _make_svc(req_repo, status_repo)
        result = await svc.check(work_item_id, uuid4(), "story")
        assert result.ok is True

    @pytest.mark.asyncio
    async def test_one_required_pending_blocks(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_req("spec_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        await status_repo.save(_vs(work_item_id, "spec_review", ValidationState.PENDING))

        svc = _make_svc(req_repo, status_repo)
        result = await svc.check(work_item_id, uuid4(), "story")
        assert result.ok is False
        assert len(result.blockers) == 1
        assert result.blockers[0].rule_id == "spec_review"

    @pytest.mark.asyncio
    async def test_only_recommended_pending_gate_passes(self) -> None:
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_req("tech_review", required=False))  # recommended only
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        await status_repo.save(_vs(work_item_id, "tech_review", ValidationState.PENDING))

        svc = _make_svc(req_repo, status_repo)
        result = await svc.check(work_item_id, uuid4(), "story")
        assert result.ok is True  # recommended rules don't block

    @pytest.mark.asyncio
    async def test_required_waived_is_blocking(self, caplog: pytest.LogCaptureFixture) -> None:
        """ALG-3: required+waived must be treated as blocking (belt-and-suspenders)."""
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_req("spec_review", required=True))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()
        await status_repo.save(_vs(work_item_id, "spec_review", ValidationState.WAIVED))

        svc = _make_svc(req_repo, status_repo)
        with caplog.at_level("WARNING"):
            result = await svc.check(work_item_id, uuid4(), "story")

        assert result.ok is False
        assert any("waived" in r.message.lower() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_missing_status_row_is_pending(self) -> None:
        """No status row = pending by default — should block."""
        req_repo = FakeValidationRequirementRepository()
        req_repo.seed(_req("spec_review"))
        work_item_id = uuid4()
        status_repo = FakeValidationStatusRepository()  # no rows

        svc = _make_svc(req_repo, status_repo)
        result = await svc.check(work_item_id, uuid4(), "story")
        assert result.ok is False
        assert result.blockers[0].status == "pending"
