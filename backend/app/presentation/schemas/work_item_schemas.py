"""Pydantic v2 request/response schemas for Work Item endpoints (EP-01 Phase 4)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.work_item import WorkItem
from app.domain.value_objects.derived_state import DerivedState
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType

# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

_NEXT_STEP: dict[WorkItemState, str | None] = {
    WorkItemState.DRAFT: "add_description_and_transition_to_in_clarification",
    WorkItemState.IN_CLARIFICATION: "complete_mandatory_sections",
    WorkItemState.IN_REVIEW: "await_reviewer_decision",
    WorkItemState.CHANGES_REQUESTED: "address_reviewer_notes",
    WorkItemState.PARTIALLY_VALIDATED: "complete_remaining_validations_or_force_ready",
    WorkItemState.READY: "ready_for_export",
    WorkItemState.EXPORTED: None,
}


class WorkItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=3, max_length=255)]
    type: WorkItemType
    project_id: UUID
    owner_id: UUID | None = None
    description: str | None = None
    original_input: str | None = None
    priority: Priority | None = None
    due_date: date | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)


class WorkItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=3, max_length=255)] | None = None
    description: str | None = None
    priority: Priority | None = None
    due_date: date | None = None
    tags: list[str] | None = None
    original_input: str | None = None


class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: WorkItemState
    reason: str | None = Field(default=None, max_length=1000)


class ForceReadyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    justification: Annotated[str, Field(min_length=10, max_length=2000)]
    confirmed: bool


class ReassignOwnerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_owner_id: UUID
    reason: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class OverrideInfo(BaseModel):
    justified: bool
    justification: str | None
    set_at: datetime | None


class WorkItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    project_id: UUID
    title: str
    type: WorkItemType
    state: WorkItemState
    priority: Priority | None
    due_date: date | None
    tags: list[str]
    description: str | None
    original_input: str | None
    owner_id: UUID
    creator_id: UUID
    completeness_score: int
    has_override: bool
    override_justification: str | None
    parent_work_item_id: UUID | None
    materialized_path: str
    attachment_count: int
    owner_suspended_flag: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    exported_at: datetime | None
    export_reference: str | None
    # Computed fields
    derived_state: DerivedState | None
    next_step: str | None
    override_info: OverrideInfo | None

    @classmethod
    def from_domain(cls, item: WorkItem, workspace_id: UUID) -> WorkItemResponse:
        override_info: OverrideInfo | None = None
        if item.has_override:
            override_info = OverrideInfo(
                justified=True,
                justification=item.override_justification,
                set_at=item.updated_at,
            )
        return cls(
            id=item.id,
            workspace_id=workspace_id,
            project_id=item.project_id,
            title=item.title,
            type=item.type,
            state=item.state,
            priority=item.priority,
            due_date=item.due_date,
            tags=item.tags,
            description=item.description,
            original_input=item.original_input,
            owner_id=item.owner_id,
            creator_id=item.creator_id,
            completeness_score=item.completeness_score,
            has_override=item.has_override,
            override_justification=item.override_justification,
            parent_work_item_id=item.parent_work_item_id,
            materialized_path=item.materialized_path,
            attachment_count=item.attachment_count,
            owner_suspended_flag=item.owner_suspended_flag,
            created_at=item.created_at,
            updated_at=item.updated_at,
            deleted_at=item.deleted_at,
            exported_at=item.exported_at,
            export_reference=item.export_reference,
            derived_state=item.derived_state,
            next_step=_NEXT_STEP.get(item.state),
            override_info=override_info,
        )


class PagedWorkItemResponse(BaseModel):
    items: list[WorkItemResponse]
    total: int
    page: int
    page_size: int
