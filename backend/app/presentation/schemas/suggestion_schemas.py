"""Pydantic request/response schemas for suggestion endpoints — EP-03 Phase 7."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus


class GenerateSuggestionsRequest(BaseModel):
    thread_id: UUID | None = None


class GenerateSuggestionsResponse(BaseModel):
    batch_id: UUID
    request_id: str | None = None


class SuggestionItemResponse(BaseModel):
    id: UUID
    work_item_id: UUID
    section_id: UUID | None
    proposed_content: str
    current_content: str
    rationale: str | None
    status: str
    batch_id: UUID
    created_at: datetime
    updated_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(cls, s: AssistantSuggestion) -> SuggestionItemResponse:
        return cls(
            id=s.id,
            work_item_id=s.work_item_id,
            section_id=s.section_id,
            proposed_content=s.proposed_content,
            current_content=s.current_content,
            rationale=s.rationale,
            status=s.status.value,
            batch_id=s.batch_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
            expires_at=s.expires_at,
        )


class PatchSuggestionStatusRequest(BaseModel):
    status: str  # "accepted" | "rejected"


class SuggestionBatchResponse(BaseModel):
    batch_id: UUID
    items: list[SuggestionItemResponse]

    @classmethod
    def from_suggestions(cls, suggestions: list[AssistantSuggestion]) -> SuggestionBatchResponse:
        if not suggestions:
            raise ValueError("Cannot build SuggestionBatchResponse from empty list")
        return cls(
            batch_id=suggestions[0].batch_id,
            items=[SuggestionItemResponse.from_domain(s) for s in suggestions],
        )


_ALLOWED_STATUS_TRANSITIONS = frozenset({"accepted", "rejected"})


def parse_suggestion_status(value: str) -> SuggestionStatus:
    """Validate and parse suggestion status from PATCH body."""
    if value not in _ALLOWED_STATUS_TRANSITIONS:
        raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUS_TRANSITIONS)}")
    return SuggestionStatus(value)
