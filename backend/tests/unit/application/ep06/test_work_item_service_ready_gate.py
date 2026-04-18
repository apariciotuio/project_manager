"""Unit tests for WorkItemService ReadyGate integration — EP-06.

Tasks: 4.22 (gate passed → state=ready), 4.22 (gate blocked → ReadyGateBlockedError).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

import app.application.services.work_item_service as _wis_module
from app.application.commands.transition_state_command import TransitionStateCommand
from app.application.events.event_bus import Event, EventBus
from app.application.services.audit_service import AuditService
from app.application.services.ready_gate_service import Blocker, GateResult
from app.application.services.work_item_service import WorkItemService
from app.domain.exceptions import ReadyGateBlockedError
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from tests.fakes.fake_repositories import (
    FakeAuditRepository,
    FakeUserRepository,
    FakeWorkItemRepository,
    FakeWorkspaceMembershipRepository,
)


class FakeEventBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.emitted: list[Event] = []

    async def emit(self, event: Event) -> None:  # type: ignore[override]
        self.emitted.append(event)


def FakeAuditService() -> AuditService:
    return AuditService(FakeAuditRepository())


def _make_ready_item(workspace_id: uuid4) -> tuple[WorkItem, uuid4]:
    """Return a fully-complete work item that passes the completeness gate."""
    owner_id = uuid4()
    item = WorkItem.create(
        title="Test item with enough title length for completeness",
        type=WorkItemType.STORY,
        owner_id=owner_id,
        creator_id=owner_id,
        project_id=None,
        description="A detailed description that is long enough to score well",
        original_input="The original user requirement text goes here and is sufficiently long",
        priority=None,
        due_date=None,
        tags=[],
        parent_work_item_id=None,
    )
    # Score is computed by compute_completeness; we need it above 80
    # Skip the completeness gate by setting score manually to 100
    item.completeness_score = 100
    return item, owner_id


class GateAlwaysPasses:
    async def check(
        self, work_item_id: object, workspace_id: object, work_item_type: str
    ) -> GateResult:
        return GateResult(ok=True, blockers=[])


class GateAlwaysBlocks:
    async def check(
        self, work_item_id: object, workspace_id: object, work_item_type: str
    ) -> GateResult:
        return GateResult(
            ok=False,
            blockers=[Blocker(rule_id="spec_review", label="Spec review", status="pending")],
        )


def _make_svc(ready_gate: object = None) -> tuple[WorkItemService, FakeWorkItemRepository, uuid4]:
    user_repo = FakeUserRepository()
    item_repo = FakeWorkItemRepository()
    membership_repo = FakeWorkspaceMembershipRepository()
    svc = WorkItemService(
        work_items=item_repo,
        users=user_repo,
        memberships=membership_repo,
        audit=FakeAuditService(),
        events=FakeEventBus(),
        ready_gate=ready_gate,
    )
    workspace_id = uuid4()
    return svc, item_repo, workspace_id


class TestReadyGateIntegration:
    """Tests use monkeypatch to set COMPLETENESS_READY_THRESHOLD=0 so the completeness
    stub (which always returns 0) doesn't block these gate-focused tests."""

    @pytest.mark.asyncio
    async def test_gate_passes_transitions_to_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_wis_module, "COMPLETENESS_READY_THRESHOLD", 0)
        svc, item_repo, workspace_id = _make_svc(ready_gate=GateAlwaysPasses())
        item, owner_id = _make_ready_item(workspace_id)
        item.state = WorkItemState.IN_CLARIFICATION
        await item_repo.save(item, workspace_id)

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=workspace_id,
            target_state=WorkItemState.READY,
            actor_id=owner_id,
            reason="all good",
        )
        saved = await svc.transition(cmd)
        assert saved.state is WorkItemState.READY

    @pytest.mark.asyncio
    async def test_gate_blocked_raises_ready_gate_blocked_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_wis_module, "COMPLETENESS_READY_THRESHOLD", 0)
        svc, item_repo, workspace_id = _make_svc(ready_gate=GateAlwaysBlocks())
        item, owner_id = _make_ready_item(workspace_id)
        item.state = WorkItemState.IN_CLARIFICATION
        await item_repo.save(item, workspace_id)

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=workspace_id,
            target_state=WorkItemState.READY,
            actor_id=owner_id,
            reason="trying to push to ready",
        )
        with pytest.raises(ReadyGateBlockedError) as exc_info:
            await svc.transition(cmd)

        assert len(exc_info.value.blockers) == 1
        assert exc_info.value.blockers[0].rule_id == "spec_review"

    @pytest.mark.asyncio
    async def test_no_gate_injected_bypasses_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ready_gate=None, only completeness gate is checked (backwards compat)."""
        monkeypatch.setattr(_wis_module, "COMPLETENESS_READY_THRESHOLD", 0)
        svc, item_repo, workspace_id = _make_svc(ready_gate=None)
        item, owner_id = _make_ready_item(workspace_id)
        item.state = WorkItemState.IN_CLARIFICATION
        await item_repo.save(item, workspace_id)

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=workspace_id,
            target_state=WorkItemState.READY,
            actor_id=owner_id,
            reason="no gate",
        )
        # Should succeed without validation gate
        saved = await svc.transition(cmd)
        assert saved.state is WorkItemState.READY
