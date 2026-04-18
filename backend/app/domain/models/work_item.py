"""WorkItem domain entity — pure, no infrastructure or ORM dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidOverrideError, InvalidTransitionError, NotOwnerError
from app.domain.state_machine import is_valid_transition
from app.domain.value_objects.derived_state import DerivedState
from app.domain.value_objects.ownership_record import OwnershipRecord
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.state_transition import StateTransition
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType

_MIN_TITLE = 3
_MAX_TITLE = 255
_MIN_JUSTIFICATION = 10


def _now() -> datetime:
    return datetime.now(UTC)


def _validate_title(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("title must not be empty")
    if len(stripped) < _MIN_TITLE:
        raise ValueError(f"title must be at least {_MIN_TITLE} characters; got {len(stripped)}")
    if len(stripped) > _MAX_TITLE:
        raise ValueError(f"title must be at most {_MAX_TITLE} characters; got {len(stripped)}")
    return stripped


@dataclass
class WorkItem:
    id: UUID
    title: str
    type: WorkItemType
    state: WorkItemState
    owner_id: UUID
    creator_id: UUID
    project_id: UUID
    description: str | None
    original_input: str | None
    priority: Priority | None
    due_date: date | None
    tags: list[str]
    completeness_score: int
    parent_work_item_id: UUID | None
    materialized_path: str
    attachment_count: int
    has_override: bool
    override_justification: str | None
    owner_suspended_flag: bool
    # EP-02 additions
    draft_data: dict | None  # type: ignore[type-arg]  # transient edit buffer, cleared on state advance
    template_id: UUID | None  # audit reference, immutable after set
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    exported_at: datetime | None
    export_reference: str | None
    external_jira_key: str | None

    @classmethod
    def create(
        cls,
        *,
        title: str,
        type: WorkItemType,
        owner_id: UUID,
        creator_id: UUID,
        project_id: UUID,
        description: str | None = None,
        original_input: str | None = None,
        priority: Priority | None = None,
        due_date: date | None = None,
        tags: list[str] | None = None,
        parent_work_item_id: UUID | None = None,
    ) -> WorkItem:
        clean_title = _validate_title(title)
        now = _now()
        return cls(
            id=uuid4(),
            title=clean_title,
            type=type,
            state=WorkItemState.DRAFT,
            owner_id=owner_id,
            creator_id=creator_id,
            project_id=project_id,
            description=description,
            original_input=original_input,
            priority=priority,
            due_date=due_date,
            tags=tags if tags is not None else [],
            completeness_score=0,
            parent_work_item_id=parent_work_item_id,
            materialized_path="",
            attachment_count=0,
            has_override=False,
            override_justification=None,
            owner_suspended_flag=False,
            draft_data=None,
            template_id=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
            exported_at=None,
            export_reference=None,
            external_jira_key=None,
        )

    @property
    def derived_state(self) -> DerivedState | None:
        if self.state == WorkItemState.EXPORTED:
            return None
        if self.state == WorkItemState.READY:
            return DerivedState.READY
        if self.owner_suspended_flag:
            return DerivedState.BLOCKED
        return DerivedState.IN_PROGRESS

    def can_transition_to(self, target: WorkItemState, actor_id: UUID) -> tuple[bool, str]:
        if actor_id != self.owner_id:
            return False, "not_owner"
        if not is_valid_transition(self.state, target):
            return False, "invalid_transition"
        return True, ""

    def apply_transition(
        self, target: WorkItemState, actor_id: UUID, reason: str | None
    ) -> StateTransition:
        if actor_id != self.owner_id:
            raise NotOwnerError(actor_id, self.id)
        if not is_valid_transition(self.state, target):
            raise InvalidTransitionError(self.state.value, target.value)
        from_state = self.state
        self.state = target
        # Clear transient draft buffer when state advances out of DRAFT (EP-02)
        if from_state == WorkItemState.DRAFT:
            self.draft_data = None
        self.updated_at = _now()
        return StateTransition(
            work_item_id=self.id,
            from_state=from_state,
            to_state=target,
            actor_id=actor_id,
            triggered_at=_now(),
            reason=reason,
            is_override=False,
            override_justification=None,
        )

    def force_ready(self, actor_id: UUID, justification: str) -> StateTransition:
        if actor_id != self.owner_id:
            raise NotOwnerError(actor_id, self.id)
        clean = justification.strip()
        if len(clean) < _MIN_JUSTIFICATION:
            raise InvalidOverrideError(
                f"justification must be at least {_MIN_JUSTIFICATION} characters"
            )
        if self.state == WorkItemState.EXPORTED:
            raise InvalidOverrideError("cannot force-ready an exported item")
        from_state = self.state
        self.state = WorkItemState.READY
        self.has_override = True
        self.override_justification = clean
        self.updated_at = _now()
        return StateTransition(
            work_item_id=self.id,
            from_state=from_state,
            to_state=WorkItemState.READY,
            actor_id=actor_id,
            triggered_at=_now(),
            reason=None,
            is_override=True,
            override_justification=clean,
        )

    def reassign_owner(
        self, new_owner_id: UUID, changed_by: UUID, reason: str | None
    ) -> OwnershipRecord:
        if new_owner_id == self.owner_id:
            raise ValueError("cannot reassign to same owner")
        previous = self.owner_id
        self.owner_id = new_owner_id
        self.updated_at = _now()
        return OwnershipRecord(
            work_item_id=self.id,
            previous_owner_id=previous,
            new_owner_id=new_owner_id,
            changed_by=changed_by,
            changed_at=_now(),
            reason=reason,
        )

    def compute_completeness(self) -> int:
        from app.domain.services.completeness_service import compute_completeness

        return compute_completeness(self)
