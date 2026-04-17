"""EP-09 — Advanced work item list filters + sort model."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class SortOption(str, Enum):
    updated_desc = "updated_desc"
    updated_asc = "updated_asc"
    created_desc = "created_desc"
    title_asc = "title_asc"
    completeness_desc = "completeness_desc"


class WorkItemListFilters(BaseModel):
    """All optional filters for GET /api/v1/work-items.

    owner_id accepts the literal string "me" — the controller resolves it to
    the authenticated user's UUID before passing to the service layer.
    After resolution, owner_id is always a UUID.

    extra="forbid" so unknown query params surface as 422.
    """

    model_config = {"extra": "forbid"}

    # Existing filters (preserved for backward compat)
    state: list[str] | None = None
    type: list[str] | None = None
    owner_id: UUID | None = None
    parent_work_item_id: UUID | None = None
    has_override: bool | None = None
    include_deleted: bool = False

    # New EP-09 filters
    project_id: UUID | None = None
    creator_id: UUID | None = None
    tag_id: list[str] | None = None  # AND semantics — item must have ALL tags
    priority: list[str] | None = None
    completeness_min: int | None = Field(default=None, ge=0, le=100)
    completeness_max: int | None = Field(default=None, ge=0, le=100)
    updated_after: datetime | None = None
    updated_before: datetime | None = None

    # Sort
    sort: SortOption = SortOption.updated_desc

    # Cursor pagination
    cursor: str | None = None
    limit: int = Field(default=25, ge=1, le=100)

    # Legacy offset pagination (preserved)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=100)

    # Free-text + puppet toggle
    q: str | None = None
    use_puppet: bool = False

    @field_validator("completeness_min", "completeness_max", mode="before")
    @classmethod
    def _clamp_completeness(cls, v: object) -> object:
        return v  # pydantic ge/le handles it

    @model_validator(mode="after")
    def _validate_completeness_range(self) -> "WorkItemListFilters":
        if (
            self.completeness_min is not None
            and self.completeness_max is not None
            and self.completeness_min > self.completeness_max
        ):
            raise ValueError("completeness_min must be <= completeness_max")
        return self
