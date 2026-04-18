"""Pydantic v2 schemas for Template endpoints — EP-02."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.work_item_type import WorkItemType

_MAX_CONTENT = 50000


class CreateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: WorkItemType
    name: Annotated[str, Field(min_length=1, max_length=255)]
    content: Annotated[str, Field(max_length=_MAX_CONTENT)]


class UpdateTemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    content: Annotated[str, Field(max_length=_MAX_CONTENT)] | None = None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID | None
    type: WorkItemType
    name: str
    content: str
    is_system: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, template: object) -> TemplateResponse:
        from app.domain.models.template import Template

        assert isinstance(template, Template)
        return cls(
            id=template.id,
            workspace_id=template.workspace_id,
            type=template.type,
            name=template.name,
            content=template.content,
            is_system=template.is_system,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
