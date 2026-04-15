"""WorkItemService — orchestrates WorkItem lifecycle.

All business rules that cross domain objects (validation gates, membership checks,
owner status checks) live here. The domain entity enforces FSM edges and field
invariants; this service enforces the "who can do what" and "when can it happen"
rules.

Fire-and-forget audit: every method calls audit.log_event() but never awaits the
result in a way that could block the caller — AuditService.log_event() never raises.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from uuid import UUID

from app.application.commands.create_work_item_command import CreateWorkItemCommand
from app.application.commands.delete_work_item_command import DeleteWorkItemCommand
from app.application.commands.force_ready_command import ForceReadyCommand
from app.application.commands.reassign_owner_command import ReassignOwnerCommand
from app.application.commands.transition_state_command import TransitionStateCommand
from app.application.commands.update_work_item_command import UpdateWorkItemCommand
from app.application.events.event_bus import EventBus
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
from app.domain.constants import COMPLETENESS_READY_THRESHOLD
from app.domain.exceptions import (
    CannotDeleteNonDraftError,
    ConfirmationRequiredError,
    CreatorNotMemberError,
    MandatoryValidationsPendingError,
    NotOwnerError,
    OwnerSuspendedError,
    TargetUserSuspendedError,
    WorkItemNotFoundError,
)
from app.domain.models.work_item import WorkItem
from app.domain.queries.page import Page
from app.domain.queries.work_item_filters import WorkItemFilters
from app.domain.repositories.user_repository import IUserRepository
from app.domain.repositories.work_item_repository import IWorkItemRepository
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)
from app.domain.services.completeness_service import compute_completeness
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.state_transition import StateTransition
from app.domain.value_objects.work_item_state import WorkItemState

logger = logging.getLogger(__name__)

_MIN_JUSTIFICATION = 10


class WorkItemService:
    def __init__(
        self,
        work_items: IWorkItemRepository,
        users: IUserRepository,
        memberships: IWorkspaceMembershipRepository,
        audit: AuditService,
        events: EventBus,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._work_items = work_items
        self._users = users
        self._memberships = memberships
        self._audit = audit
        self._events = events
        self._clock = clock

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    async def create(self, cmd: CreateWorkItemCommand) -> WorkItem:
        effective_owner_id = cmd.owner_id if cmd.owner_id is not None else cmd.creator_id

        # Verify owner is active
        owner = await self._users.get_by_id(effective_owner_id)
        if owner is None or owner.status != "active":
            logger.warning(
                "work_item.blocked_by_suspended_user",
                extra={
                    "user_id": str(effective_owner_id),
                    "workspace_id": str(cmd.workspace_id),
                },
            )
            raise OwnerSuspendedError(effective_owner_id)

        # Verify creator has active membership in the workspace
        creator_memberships = await self._memberships.get_active_by_user_id(cmd.creator_id)
        if not any(m.workspace_id == cmd.workspace_id for m in creator_memberships):
            raise CreatorNotMemberError(cmd.creator_id, cmd.workspace_id)

        item = WorkItem.create(
            title=cmd.title,
            type=cmd.type,
            owner_id=effective_owner_id,
            creator_id=cmd.creator_id,
            project_id=cmd.project_id,
            description=cmd.description,
            original_input=cmd.original_input,
            priority=cmd.priority,
            due_date=cmd.due_date,
            tags=list(cmd.tags),
        )
        item.completeness_score = compute_completeness(item)

        saved = await self._work_items.save(item, cmd.workspace_id)

        creation_transition = StateTransition(
            work_item_id=saved.id,
            from_state=WorkItemState.DRAFT,  # sentinel for "initial creation"
            to_state=WorkItemState.DRAFT,
            actor_id=cmd.creator_id,
            triggered_at=self._clock(),
            reason="work item created",
            is_override=False,
            override_justification=None,
        )
        await self._work_items.record_transition(creation_transition, cmd.workspace_id)

        await self._events.emit(
            WorkItemCreatedEvent(
                work_item_id=saved.id,
                workspace_id=cmd.workspace_id,
                type=saved.type,
                creator_id=cmd.creator_id,
                owner_id=effective_owner_id,
            )
        )
        await self._audit.log_event(
            category="domain",
            action="work_item_created",
            actor_id=cmd.creator_id,
            workspace_id=cmd.workspace_id,
            context={"item_id": str(saved.id), "type": saved.type.value},
        )
        return saved

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    async def get(self, item_id: UUID, workspace_id: UUID) -> WorkItem:
        item = await self._work_items.get(item_id, workspace_id)
        if item is None:
            raise WorkItemNotFoundError(item_id)
        return item

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    async def list(
        self,
        workspace_id: UUID,
        project_id: UUID,
        filters: WorkItemFilters,
    ) -> Page[WorkItem]:
        return await self._work_items.list(workspace_id, project_id, filters)

    # ------------------------------------------------------------------
    # update
    # ------------------------------------------------------------------

    async def update(self, cmd: UpdateWorkItemCommand) -> WorkItem:
        item = await self._get_or_raise(cmd.item_id, cmd.workspace_id)

        # Detect content field changes when item is READY
        changed_fields: list[str] = []

        if item.state == WorkItemState.READY:
            if cmd.title is not None and cmd.title != item.title:
                changed_fields.append("title")
            if cmd.description is not None and cmd.description != item.description:
                changed_fields.append("description")
            if cmd.original_input is not None and cmd.original_input != item.original_input:
                changed_fields.append("original_input")
            if cmd.priority is not None and cmd.priority != item.priority:
                changed_fields.append("priority")
            if cmd.due_date is not None and cmd.due_date != item.due_date:
                changed_fields.append("due_date")
            if cmd.tags is not None and list(cmd.tags) != item.tags:
                changed_fields.append("tags")

        if changed_fields and item.state == WorkItemState.READY:
            # Emit content-changed event before the revert
            await self._events.emit(
                WorkItemContentChangedAfterReadyEvent(
                    work_item_id=item.id,
                    workspace_id=cmd.workspace_id,
                    actor_id=cmd.actor_id,
                    changed_fields=tuple(changed_fields),
                )
            )
            # Auto-revert to IN_CLARIFICATION — system actor
            from_state = item.state
            item.state = WorkItemState.IN_CLARIFICATION
            item.has_override = False
            item.override_justification = None
            item.updated_at = self._clock()

            revert_transition = StateTransition(
                work_item_id=item.id,
                from_state=from_state,
                to_state=WorkItemState.IN_CLARIFICATION,
                actor_id=None,  # system actor
                triggered_at=self._clock(),
                reason="auto-revert after content change",
                is_override=False,
                override_justification=None,
            )
            await self._work_items.record_transition(revert_transition, cmd.workspace_id)

            await self._events.emit(
                WorkItemRevertedFromReadyEvent(
                    work_item_id=item.id,
                    workspace_id=cmd.workspace_id,
                    actor_id=None,  # system-triggered
                    reason="auto-revert after content change",
                )
            )

        # Apply field updates
        if cmd.title is not None:
            item.title = cmd.title
        if cmd.description is not None:
            item.description = cmd.description
        if cmd.original_input is not None:
            item.original_input = cmd.original_input
        if cmd.priority is not None:
            item.priority = cmd.priority
        if cmd.due_date is not None:
            item.due_date = cmd.due_date
        if cmd.tags is not None:
            item.tags = list(cmd.tags)

        item.completeness_score = compute_completeness(item)
        item.updated_at = self._clock()

        saved = await self._work_items.save(item, cmd.workspace_id)
        await self._audit.log_event(
            category="domain",
            action="work_item_updated",
            actor_id=cmd.actor_id,
            workspace_id=cmd.workspace_id,
            context={"item_id": str(item.id), "changed_fields": changed_fields},
        )
        return saved

    # ------------------------------------------------------------------
    # transition
    # ------------------------------------------------------------------

    async def transition(self, cmd: TransitionStateCommand) -> WorkItem:
        item = await self._get_or_raise(cmd.item_id, cmd.workspace_id)

        # Gate: completeness check before transitioning to READY
        if cmd.target_state == WorkItemState.READY:
            score = compute_completeness(item)
            if score < COMPLETENESS_READY_THRESHOLD:
                raise MandatoryValidationsPendingError(
                    item.id, pending_ids=(score,)
                )

        # apply_transition enforces ownership and FSM edges
        transition = item.apply_transition(cmd.target_state, cmd.actor_id, cmd.reason)

        saved = await self._work_items.save(item, cmd.workspace_id)
        await self._work_items.record_transition(transition, cmd.workspace_id)

        logger.info(
            "work_item.transition",
            extra={
                "item_id": str(saved.id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "actor_id": str(cmd.actor_id),
                "workspace_id": str(cmd.workspace_id),
            },
        )

        await self._events.emit(
            WorkItemStateChangedEvent(
                work_item_id=saved.id,
                workspace_id=cmd.workspace_id,
                from_state=transition.from_state,
                to_state=transition.to_state,
                actor_id=cmd.actor_id,
                is_override=False,
                reason=cmd.reason,
            )
        )

        if cmd.target_state == WorkItemState.CHANGES_REQUESTED:
            await self._events.emit(
                WorkItemChangesRequestedEvent(
                    work_item_id=saved.id,
                    workspace_id=cmd.workspace_id,
                    reviewer_id=cmd.actor_id,
                    notes=cmd.reason,
                )
            )

        await self._audit.log_event(
            category="domain",
            action="work_item_state_changed",
            actor_id=cmd.actor_id,
            workspace_id=cmd.workspace_id,
            context={
                "item_id": str(saved.id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
            },
        )
        return saved

    # ------------------------------------------------------------------
    # force_ready
    # ------------------------------------------------------------------

    async def force_ready(self, cmd: ForceReadyCommand) -> WorkItem:
        if len(cmd.justification.strip()) < _MIN_JUSTIFICATION:
            raise ValueError(
                f"justification must be at least {_MIN_JUSTIFICATION} characters"
            )

        item = await self._get_or_raise(cmd.item_id, cmd.workspace_id)

        if not cmd.confirmed:
            score = compute_completeness(item)
            raise ConfirmationRequiredError(pending_ids=(score,))

        # force_ready() enforces ownership and validates justification length
        transition = item.force_ready(cmd.actor_id, cmd.justification)

        saved = await self._work_items.save(item, cmd.workspace_id)
        await self._work_items.record_transition(transition, cmd.workspace_id)

        logger.warning(
            "work_item.override",
            extra={
                "item_id": str(saved.id),
                "actor_id": str(cmd.actor_id),
                "workspace_id": str(cmd.workspace_id),
                "justification": cmd.justification[:200],
            },
        )

        await self._events.emit(
            WorkItemReadyOverrideEvent(
                work_item_id=saved.id,
                workspace_id=cmd.workspace_id,
                actor_id=cmd.actor_id,
                justification=cmd.justification,
            )
        )
        await self._events.emit(
            WorkItemStateChangedEvent(
                work_item_id=saved.id,
                workspace_id=cmd.workspace_id,
                from_state=transition.from_state,
                to_state=transition.to_state,
                actor_id=cmd.actor_id,
                is_override=True,
                reason=cmd.justification,
            )
        )

        await self._audit.log_event(
            category="domain",
            action="work_item_force_ready",
            actor_id=cmd.actor_id,
            workspace_id=cmd.workspace_id,
            context={
                "item_id": str(saved.id),
                "justification": cmd.justification[:200],
            },
        )
        return saved

    # ------------------------------------------------------------------
    # reassign
    # ------------------------------------------------------------------

    async def reassign(self, cmd: ReassignOwnerCommand) -> WorkItem:
        item = await self._get_or_raise(cmd.item_id, cmd.workspace_id)

        if item.owner_id != cmd.actor_id:
            raise NotOwnerError(cmd.actor_id, cmd.item_id)

        target = await self._users.get_by_id(cmd.new_owner_id)
        if target is None or target.status != "active":
            logger.warning(
                "work_item.blocked_by_suspended_user",
                extra={
                    "user_id": str(cmd.new_owner_id),
                    "item_id": str(cmd.item_id),
                },
            )
            raise TargetUserSuspendedError(cmd.new_owner_id)

        ownership_record = item.reassign_owner(cmd.new_owner_id, cmd.actor_id, cmd.reason)
        previous_owner_id = ownership_record.previous_owner_id

        saved = await self._work_items.save(item, cmd.workspace_id)
        await self._work_items.record_ownership_change(
            ownership_record, cmd.workspace_id, previous_owner_id=previous_owner_id
        )

        await self._events.emit(
            WorkItemOwnerChangedEvent(
                work_item_id=saved.id,
                workspace_id=cmd.workspace_id,
                previous_owner_id=previous_owner_id,
                new_owner_id=cmd.new_owner_id,
                changed_by=cmd.actor_id,
                reason=cmd.reason,
            )
        )

        await self._audit.log_event(
            category="domain",
            action="work_item_owner_changed",
            actor_id=cmd.actor_id,
            workspace_id=cmd.workspace_id,
            context={
                "item_id": str(saved.id),
                "previous_owner_id": str(previous_owner_id),
                "new_owner_id": str(cmd.new_owner_id),
            },
        )
        return saved

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    async def delete(self, cmd: DeleteWorkItemCommand) -> None:
        item = await self._get_or_raise(cmd.item_id, cmd.workspace_id)

        if item.state != WorkItemState.DRAFT:
            raise CannotDeleteNonDraftError(cmd.item_id, item.state.value)

        if item.owner_id != cmd.actor_id:
            raise NotOwnerError(cmd.actor_id, cmd.item_id)

        item.deleted_at = self._clock()
        await self._work_items.save(item, cmd.workspace_id)

        await self._audit.log_event(
            category="domain",
            action="work_item_deleted",
            actor_id=cmd.actor_id,
            workspace_id=cmd.workspace_id,
            context={"item_id": str(cmd.item_id)},
        )

    # ------------------------------------------------------------------
    # get_transitions / get_ownership_history
    # ------------------------------------------------------------------

    async def get_transitions(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[StateTransition]:
        await self._get_or_raise(item_id, workspace_id)
        return await self._work_items.get_transitions(item_id, workspace_id)

    async def get_ownership_history(
        self, item_id: UUID, workspace_id: UUID
    ) -> Sequence[OwnershipRecord]:
        await self._get_or_raise(item_id, workspace_id)
        return await self._work_items.get_ownership_history(item_id, workspace_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    async def _get_or_raise(self, item_id: UUID, workspace_id: UUID) -> WorkItem:
        item = await self._work_items.get(item_id, workspace_id)
        if item is None:
            raise WorkItemNotFoundError(item_id)
        return item
