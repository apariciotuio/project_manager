"""Pydantic request schemas for the Dundun async callback endpoint — EP-03."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SuggestionItem(BaseModel):
    section_id: UUID | None = None
    proposed_content: str
    current_content: str
    rationale: str | None = None


class GapFindingPayload(BaseModel):
    dimension: str
    severity: Literal["blocking", "warning", "info"]
    message: str


class QuickActionResult(BaseModel):
    section_id: UUID | None = None
    new_content: str


class DundunCallbackRequest(BaseModel):
    agent: Literal["wm_suggestion_agent", "wm_gap_agent", "wm_quick_action_agent"]
    request_id: str
    status: Literal["success", "error"]
    work_item_id: UUID | None = None
    batch_id: UUID | None = None
    user_id: UUID | None = None
    # Agent-specific payloads
    suggestions: list[SuggestionItem] | None = None
    gap_findings: list[GapFindingPayload] | None = None
    quick_action_result: QuickActionResult | None = None
    error_message: str | None = None
