"""WorkItemService unit tests.

All collaborators are fakes — no DB, no HTTP.
Each test class covers one service method. At least 2-3 variations per behavior.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.commands.create_work_item_command import CreateWorkItemCommand
from app.application.commands.delete_work_item_command import DeleteWorkItemCommand
from app.application.commands.force_ready_command import ForceReadyCommand
from app.application.commands.reassign_owner_command import ReassignOwnerCommand
from app.application.commands.transition_state_command import TransitionStateCommand
from app.application.commands.update_work_item_command import UpdateWorkItemCommand
from app.application.events.event_bus import Event, EventBus
from app.application.events.events import (
    WorkItemChangesRequestedEvent,
    WorkItemContentChangedAfterReadyEvent,
    WorkItemCreatedEvent,
    WorkItemOwnerChangedEvent,
    WorkItemReadyOverrideEvent,
    WorkItemRevertedFromReadyEvent,
    WorkItemStateChangedEvent,
)
from app.application.services.audit_service import AuditService
from app.application.services.work_item_service import WorkItemService
from app.domain.exceptions import (
    CannotDeleteNonDraftError,
    ConfirmationRequiredError,
    CreatorNotMemberError,
    InvalidTransitionError,
    MandatoryValidationsPendingError,
    NotOwnerError,
    OwnerSuspendedError,
    TargetUserSuspendedError,
    WorkItemNotFoundError,
)
from app.domain.models.user import User
from app.domain.models.work_item import WorkItem
from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from tests.fakes.fake_repositories import (
    FakeAuditRepository,
    FakeUserRepository,
    FakeWorkItemRepository,
    FakeWorkspaceMembershipRepository,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_user(status: str = "active") -> User:
    u = User.from_google_claims(
        sub=f"sub-{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@example.com",
        name="Test User",
        picture=None,
    )
    u.status = status
    return u


def _make_membership(workspace_id: Any, user_id: Any) -> WorkspaceMembership:
    return WorkspaceMembership.create(
        workspace_id=workspace_id, user_id=user_id, role="member", is_default=True
    )


def _recording_bus() -> tuple[EventBus, list[Event]]:
    bus = EventBus()
    recorded: list[Event] = []

    async def recorder(event: Event) -> None:
        recorded.append(event)

    for etype in (
        WorkItemCreatedEvent,
        WorkItemStateChangedEvent,
        WorkItemReadyOverrideEvent,
        WorkItemRevertedFromReadyEvent,
        WorkItemOwnerChangedEvent,
        WorkItemChangesRequestedEvent,
        WorkItemContentChangedAfterReadyEvent,
    ):
        bus.subscribe(etype, recorder)

    return bus, recorded


def _make_service(
    work_items: FakeWorkItemRepository | None = None,
    users: FakeUserRepository | None = None,
    memberships: FakeWorkspaceMembershipRepository | None = None,
    bus: EventBus | None = None,
) -> tuple[WorkItemService, FakeWorkItemRepository, list[Event], FakeAuditRepository]:
    wi_repo = work_items or FakeWorkItemRepository()
    user_repo = users or FakeUserRepository()
    mem_repo = memberships or FakeWorkspaceMembershipRepository()
    audit_repo = FakeAuditRepository()
    audit_svc = AuditService(audit_repo)
    if bus is None:
        bus, recorded = _recording_bus()
    else:
        recorded = []
    svc = WorkItemService(wi_repo, user_repo, mem_repo, audit_svc, bus)
    return svc, wi_repo, recorded, audit_repo


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_defaults_owner_to_creator(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        await user_repo.upsert(creator)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, creator.id))

        svc, wi_repo, events, _ = _make_service(users=user_repo, memberships=mem_repo)
        cmd = CreateWorkItemCommand(
            title="Test item",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
            # owner_id omitted
        )
        item = await svc.create(cmd)

        assert item.owner_id == creator.id
        assert item.state == WorkItemState.DRAFT

    @pytest.mark.asyncio
    async def test_create_uses_explicit_owner_id(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        owner = _make_user()
        await user_repo.upsert(creator)
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, creator.id))

        svc, _, events, _ = _make_service(users=user_repo, memberships=mem_repo)
        cmd = CreateWorkItemCommand(
            title="Test item",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
            owner_id=owner.id,
        )
        item = await svc.create(cmd)

        assert item.owner_id == owner.id

    @pytest.mark.asyncio
    async def test_create_emits_work_item_created_event(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        await user_repo.upsert(creator)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, creator.id))

        bus, recorded = _recording_bus()
        svc, _, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)
        cmd = CreateWorkItemCommand(
            title="Event test",
            type=WorkItemType.TASK,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
        )
        item = await svc.create(cmd)

        created_events = [e for e in recorded if isinstance(e, WorkItemCreatedEvent)]
        assert len(created_events) == 1
        assert created_events[0].work_item_id == item.id

    @pytest.mark.asyncio
    async def test_create_raises_owner_suspended_error_for_suspended_owner(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        suspended_owner = _make_user(status="suspended")
        await user_repo.upsert(creator)
        await user_repo.upsert(suspended_owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, creator.id))

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)
        cmd = CreateWorkItemCommand(
            title="Should fail",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
            owner_id=suspended_owner.id,
        )
        with pytest.raises(OwnerSuspendedError) as exc:
            await svc.create(cmd)

        assert exc.value.owner_id == suspended_owner.id
        # No item persisted
        assert len(wi_repo._items) == 0

    @pytest.mark.asyncio
    async def test_create_raises_owner_suspended_when_creator_is_suspended(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        deleted_user = _make_user(status="deleted")
        await user_repo.upsert(deleted_user)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)
        cmd = CreateWorkItemCommand(
            title="Should fail",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=deleted_user.id,
            # no explicit owner_id → defaults to creator
        )
        with pytest.raises(OwnerSuspendedError):
            await svc.create(cmd)

    @pytest.mark.asyncio
    async def test_create_raises_creator_not_member_when_not_in_workspace(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        await user_repo.upsert(creator)
        # No membership created

        svc, _, _, _ = _make_service(users=user_repo, memberships=mem_repo)
        ws_id = uuid4()
        cmd = CreateWorkItemCommand(
            title="Should fail",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
        )
        with pytest.raises(CreatorNotMemberError) as exc:
            await svc.create(cmd)

        assert exc.value.creator_id == creator.id
        assert exc.value.workspace_id == ws_id

    @pytest.mark.asyncio
    async def test_create_records_initial_transition(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        creator = _make_user()
        await user_repo.upsert(creator)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, creator.id))

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)
        cmd = CreateWorkItemCommand(
            title="Transition test",
            type=WorkItemType.BUG,
            workspace_id=ws_id,
            project_id=uuid4(),
            creator_id=creator.id,
        )
        item = await svc.create(cmd)

        assert len(wi_repo.transitions) == 1
        assert wi_repo.transitions[0].work_item_id == item.id


# ---------------------------------------------------------------------------
# transition
# ---------------------------------------------------------------------------


class TestTransition:
    async def _setup(
        self,
    ) -> tuple[WorkItemService, FakeWorkItemRepository, list[Event], User, uuid4, WorkItem]:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Test item",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        return svc, wi_repo, recorded, owner, ws_id, item

    @pytest.mark.asyncio
    async def test_valid_transition_succeeds_and_emits_event(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._setup()

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=ws_id,
            target_state=WorkItemState.IN_CLARIFICATION,
            actor_id=owner.id,
        )
        updated = await svc.transition(cmd)

        assert updated.state == WorkItemState.IN_CLARIFICATION
        state_events = [e for e in recorded if isinstance(e, WorkItemStateChangedEvent)]
        assert len(state_events) == 1
        assert state_events[0].to_state == WorkItemState.IN_CLARIFICATION

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_and_no_row_inserted(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._setup()
        initial_transition_count = len(wi_repo.transitions)

        # DRAFT → IN_REVIEW is invalid
        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=ws_id,
            target_state=WorkItemState.IN_REVIEW,
            actor_id=owner.id,
        )
        with pytest.raises(InvalidTransitionError):
            await svc.transition(cmd)

        assert len(wi_repo.transitions) == initial_transition_count

    @pytest.mark.asyncio
    async def test_non_owner_raises_not_owner_error(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._setup()
        non_owner = uuid4()

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=ws_id,
            target_state=WorkItemState.IN_CLARIFICATION,
            actor_id=non_owner,
        )
        with pytest.raises(NotOwnerError):
            await svc.transition(cmd)

    @pytest.mark.asyncio
    async def test_transition_to_ready_raises_mandatory_validations_pending(self) -> None:
        """Completeness is stubbed at 0 which is below the 80 threshold."""
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        # Put item in IN_CLARIFICATION so READY is a valid FSM edge
        item = WorkItem.create(
            title="Ready test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.IN_CLARIFICATION
        await wi_repo.save(item, ws_id)

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=ws_id,
            target_state=WorkItemState.READY,
            actor_id=owner.id,
        )
        with pytest.raises(MandatoryValidationsPendingError) as exc:
            await svc.transition(cmd)

        assert exc.value.pending_ids == (40,)  # title(25) + owner(15)

    @pytest.mark.asyncio
    async def test_transition_changes_requested_emits_extra_event(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="CR test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.IN_CLARIFICATION
        await wi_repo.save(item, ws_id)

        cmd = TransitionStateCommand(
            item_id=item.id,
            workspace_id=ws_id,
            target_state=WorkItemState.CHANGES_REQUESTED,
            actor_id=owner.id,
            reason="needs more info",
        )
        await svc.transition(cmd)

        cr_events = [e for e in recorded if isinstance(e, WorkItemChangesRequestedEvent)]
        assert len(cr_events) == 1
        assert cr_events[0].reviewer_id == owner.id
        assert cr_events[0].notes == "needs more info"

    @pytest.mark.asyncio
    async def test_transition_work_item_not_found_raises(self) -> None:
        svc, _, _, _ = _make_service()
        cmd = TransitionStateCommand(
            item_id=uuid4(),
            workspace_id=uuid4(),
            target_state=WorkItemState.IN_CLARIFICATION,
            actor_id=uuid4(),
        )
        with pytest.raises(WorkItemNotFoundError):
            await svc.transition(cmd)


# ---------------------------------------------------------------------------
# force_ready
# ---------------------------------------------------------------------------


class TestForceReady:
    async def _setup_in_clarification(
        self,
    ) -> tuple[WorkItemService, FakeWorkItemRepository, list[Event], User, Any, WorkItem]:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Force ready test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.IN_CLARIFICATION
        await wi_repo.save(item, ws_id)

        return svc, wi_repo, recorded, owner, ws_id, item

    @pytest.mark.asyncio
    async def test_force_ready_short_justification_raises_value_error(self) -> None:
        svc, _, _, owner, ws_id, item = await self._setup_in_clarification()

        for short_just in ("", "short", "nine chr"):
            cmd = ForceReadyCommand(
                item_id=item.id,
                workspace_id=ws_id,
                actor_id=owner.id,
                justification=short_just,
                confirmed=True,
            )
            with pytest.raises(ValueError):
                await svc.force_ready(cmd)

    @pytest.mark.asyncio
    async def test_force_ready_not_confirmed_raises_confirmation_required(self) -> None:
        svc, _, _, owner, ws_id, item = await self._setup_in_clarification()

        cmd = ForceReadyCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            justification="reason text here that is long enough",
            confirmed=False,
        )
        with pytest.raises(ConfirmationRequiredError):
            await svc.force_ready(cmd)

    @pytest.mark.asyncio
    async def test_force_ready_non_owner_raises_not_owner_error(self) -> None:
        svc, _, _, owner, ws_id, item = await self._setup_in_clarification()

        cmd = ForceReadyCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=uuid4(),  # not the owner
            justification="justification long enough here",
            confirmed=True,
        )
        with pytest.raises(NotOwnerError):
            await svc.force_ready(cmd)

    @pytest.mark.asyncio
    async def test_force_ready_sets_has_override_and_emits_events(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Force ready",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.IN_CLARIFICATION
        await wi_repo.save(item, ws_id)

        cmd = ForceReadyCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            justification="Shipping this week, deferring review",
            confirmed=True,
        )
        result = await svc.force_ready(cmd)

        assert result.has_override is True
        assert result.override_justification == "Shipping this week, deferring review"
        assert result.state == WorkItemState.READY

        override_events = [e for e in recorded if isinstance(e, WorkItemReadyOverrideEvent)]
        state_events = [e for e in recorded if isinstance(e, WorkItemStateChangedEvent)]
        assert len(override_events) == 1
        assert len(state_events) == 1
        assert state_events[0].is_override is True

    @pytest.mark.asyncio
    async def test_force_ready_records_transition(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._setup_in_clarification()

        cmd = ForceReadyCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            justification="Long enough justification text",
            confirmed=True,
        )
        await svc.force_ready(cmd)

        transitions = [t for t in wi_repo.transitions if t.work_item_id == item.id]
        assert len(transitions) == 1
        assert transitions[0].is_override is True


# ---------------------------------------------------------------------------
# reassign
# ---------------------------------------------------------------------------


class TestReassign:
    @pytest.mark.asyncio
    async def test_owner_can_reassign(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        new_owner = _make_user()
        await user_repo.upsert(owner)
        await user_repo.upsert(new_owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Reassign test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = ReassignOwnerCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            new_owner_id=new_owner.id,
        )
        result = await svc.reassign(cmd)

        assert result.owner_id == new_owner.id
        owner_events = [e for e in recorded if isinstance(e, WorkItemOwnerChangedEvent)]
        assert len(owner_events) == 1
        assert owner_events[0].new_owner_id == new_owner.id

    @pytest.mark.asyncio
    async def test_non_owner_reassign_raises_not_owner_error(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        other = _make_user()
        new_owner = _make_user()
        await user_repo.upsert(owner)
        await user_repo.upsert(other)
        await user_repo.upsert(new_owner)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        item = WorkItem.create(
            title="Non-owner test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = ReassignOwnerCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=other.id,  # not the owner
            new_owner_id=new_owner.id,
        )
        with pytest.raises(NotOwnerError):
            await svc.reassign(cmd)

    @pytest.mark.asyncio
    async def test_reassign_suspended_target_raises_target_user_suspended(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        suspended = _make_user(status="suspended")
        await user_repo.upsert(owner)
        await user_repo.upsert(suspended)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        item = WorkItem.create(
            title="Suspended target",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = ReassignOwnerCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            new_owner_id=suspended.id,
        )
        with pytest.raises(TargetUserSuspendedError):
            await svc.reassign(cmd)

    @pytest.mark.asyncio
    async def test_reassign_records_ownership_change(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        new_owner = _make_user()
        await user_repo.upsert(owner)
        await user_repo.upsert(new_owner)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        item = WorkItem.create(
            title="Ownership record test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = ReassignOwnerCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            new_owner_id=new_owner.id,
            reason="team restructure",
        )
        await svc.reassign(cmd)

        assert len(wi_repo.ownership_records) == 1
        rec = wi_repo.ownership_records[0]
        assert rec.previous_owner_id == owner.id
        assert rec.new_owner_id == new_owner.id
        assert rec.reason == "team restructure"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_draft_item_soft_deletes(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        item = WorkItem.create(
            title="Delete test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = DeleteWorkItemCommand(item_id=item.id, workspace_id=ws_id, actor_id=owner.id)
        await svc.delete(cmd)

        saved = wi_repo._items.get((ws_id, item.id))
        assert saved is not None
        assert saved.deleted_at is not None

    @pytest.mark.asyncio
    async def test_delete_non_draft_raises_cannot_delete_non_draft(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        for non_draft_state in (
            WorkItemState.IN_CLARIFICATION,
            WorkItemState.IN_REVIEW,
            WorkItemState.READY,
        ):
            item = WorkItem.create(
                title="Non-draft delete test",
                type=WorkItemType.BUG,
                owner_id=owner.id,
                creator_id=owner.id,
                project_id=uuid4(),
            )
            item.state = non_draft_state
            await wi_repo.save(item, ws_id)

            cmd = DeleteWorkItemCommand(item_id=item.id, workspace_id=ws_id, actor_id=owner.id)
            with pytest.raises(CannotDeleteNonDraftError):
                await svc.delete(cmd)

    @pytest.mark.asyncio
    async def test_delete_non_owner_raises_not_owner_error(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        other = _make_user()
        await user_repo.upsert(owner)
        await user_repo.upsert(other)
        ws_id = uuid4()

        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo)

        item = WorkItem.create(
            title="Owner delete test",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        await wi_repo.save(item, ws_id)

        cmd = DeleteWorkItemCommand(item_id=item.id, workspace_id=ws_id, actor_id=other.id)
        with pytest.raises(NotOwnerError):
            await svc.delete(cmd)


# ---------------------------------------------------------------------------
# update (content change on READY auto-revert)
# ---------------------------------------------------------------------------


class TestUpdate:
    async def _ready_item(
        self,
    ) -> tuple[WorkItemService, FakeWorkItemRepository, list[Event], User, Any, WorkItem]:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Original title",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.READY
        item.has_override = True
        item.override_justification = "was justified"
        await wi_repo.save(item, ws_id)

        return svc, wi_repo, recorded, owner, ws_id, item

    @pytest.mark.asyncio
    async def test_content_update_on_ready_reverts_to_in_clarification(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._ready_item()

        cmd = UpdateWorkItemCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            title="New title",
        )
        result = await svc.update(cmd)

        assert result.state == WorkItemState.IN_CLARIFICATION
        assert result.has_override is False
        assert result.override_justification is None
        assert result.title == "New title"

    @pytest.mark.asyncio
    async def test_content_update_on_ready_emits_content_changed_and_reverted_events(
        self,
    ) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._ready_item()

        cmd = UpdateWorkItemCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            title="Changed title",
        )
        await svc.update(cmd)

        content_events = [
            e for e in recorded if isinstance(e, WorkItemContentChangedAfterReadyEvent)
        ]
        revert_events = [e for e in recorded if isinstance(e, WorkItemRevertedFromReadyEvent)]
        assert len(content_events) == 1
        assert "title" in content_events[0].changed_fields
        assert len(revert_events) == 1

    @pytest.mark.asyncio
    async def test_content_update_on_ready_records_system_transition(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._ready_item()

        cmd = UpdateWorkItemCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            description="New description",
        )
        await svc.update(cmd)

        system_transitions = [
            t for t in wi_repo.transitions if t.work_item_id == item.id and t.actor_id is None
        ]
        assert len(system_transitions) == 1
        assert system_transitions[0].to_state == WorkItemState.IN_CLARIFICATION

    @pytest.mark.asyncio
    async def test_non_content_field_update_on_non_ready_no_revert(self) -> None:
        user_repo = FakeUserRepository()
        mem_repo = FakeWorkspaceMembershipRepository()
        owner = _make_user()
        await user_repo.upsert(owner)
        ws_id = uuid4()
        await mem_repo.create(_make_membership(ws_id, owner.id))

        bus, recorded = _recording_bus()
        svc, wi_repo, _, _ = _make_service(users=user_repo, memberships=mem_repo, bus=bus)

        item = WorkItem.create(
            title="Draft item",
            type=WorkItemType.BUG,
            owner_id=owner.id,
            creator_id=owner.id,
            project_id=uuid4(),
        )
        item.state = WorkItemState.IN_CLARIFICATION
        await wi_repo.save(item, ws_id)

        cmd = UpdateWorkItemCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            title="Updated title in clarification",
        )
        result = await svc.update(cmd)

        assert result.state == WorkItemState.IN_CLARIFICATION
        content_events = [
            e for e in recorded if isinstance(e, WorkItemContentChangedAfterReadyEvent)
        ]
        assert len(content_events) == 0

    @pytest.mark.asyncio
    async def test_update_priority_on_ready_triggers_revert(self) -> None:
        svc, wi_repo, recorded, owner, ws_id, item = await self._ready_item()

        cmd = UpdateWorkItemCommand(
            item_id=item.id,
            workspace_id=ws_id,
            actor_id=owner.id,
            priority=Priority.HIGH,
        )
        result = await svc.update(cmd)

        assert result.state == WorkItemState.IN_CLARIFICATION
        content_events = [
            e for e in recorded if isinstance(e, WorkItemContentChangedAfterReadyEvent)
        ]
        assert "priority" in content_events[0].changed_fields
