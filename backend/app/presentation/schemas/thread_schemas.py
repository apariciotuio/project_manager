"""Pydantic request/response schemas for conversation thread endpoints — EP-03 Phase 7."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.models.conversation_thread import ConversationThread


class CreateThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_item_id: UUID | None = None


class ThreadResponse(BaseModel):
    id: UUID
    user_id: UUID
    work_item_id: UUID | None
    dundun_conversation_id: str
    last_message_preview: str | None
    last_message_at: datetime | None
    created_at: datetime
    is_archived: bool

    @classmethod
    def from_domain(cls, thread: ConversationThread) -> ThreadResponse:
        return cls(
            id=thread.id,
            user_id=thread.user_id,
            work_item_id=thread.work_item_id,
            dundun_conversation_id=thread.dundun_conversation_id,
            last_message_preview=thread.last_message_preview,
            last_message_at=thread.last_message_at,
            created_at=thread.created_at,
            is_archived=thread.is_archived,
        )
