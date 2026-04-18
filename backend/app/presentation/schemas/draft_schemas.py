"""Pydantic v2 schemas for WorkItemDraft endpoints — EP-02."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

_MAX_DRAFT_DATA_SIZE = 65536  # 64KB guard — reject strings over this limit in draft_data


class UpsertDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    data: dict[str, Any] = Field(default_factory=dict)
    local_version: int = Field(ge=0)


class SaveCommittedDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_data: dict[str, Any] = Field(default_factory=dict)


class WorkItemDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    workspace_id: UUID
    data: dict[str, Any]
    local_version: int
    incomplete: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(cls, draft: object) -> WorkItemDraftResponse:
        from app.domain.models.work_item_draft import WorkItemDraft

        assert isinstance(draft, WorkItemDraft)
        return cls(
            id=draft.id,
            user_id=draft.user_id,
            workspace_id=draft.workspace_id,
            data=draft.data,
            local_version=draft.local_version,
            incomplete=draft.incomplete,
            created_at=draft.created_at,
            updated_at=draft.updated_at,
            expires_at=draft.expires_at,
        )
