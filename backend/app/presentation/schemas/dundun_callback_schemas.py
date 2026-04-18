"""Pydantic request schemas for the Dundun async callback endpoint — EP-03."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

# External Dundun webhook payloads — extra fields are ignored rather than
# rejected so a future Dundun agent adding a field does not 422 our callback.
# HMAC + request_id idempotency are the trust gates on this surface.
_WEBHOOK_CONFIG = ConfigDict(extra="ignore")


class SuggestionItem(BaseModel):
    model_config = _WEBHOOK_CONFIG

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


class SectionPayload(BaseModel):
    """One section returned by the spec-gen agent."""

    dimension: str
    content: str


class BreakdownItem(BaseModel):
    """One task node emitted by wm_breakdown_agent."""

    title: str
    parent_title: str | None = None
    description: str = ""


class DundunCallbackRequest(BaseModel):
    model_config = _WEBHOOK_CONFIG

    agent: Literal[
        "wm_suggestion_agent",
        "wm_gap_agent",
        "wm_quick_action_agent",
        "wm_spec_gen_agent",
        "wm_breakdown_agent",
    ]
    request_id: str
    status: Literal["success", "error"]
    work_item_id: UUID | None = None
    batch_id: UUID | None = None
    user_id: UUID | None = None
    # Agent-specific payloads
    suggestions: list[SuggestionItem] | None = None
    gap_findings: list[GapFindingPayload] | None = None
    quick_action_result: QuickActionResult | None = None
    # wm_spec_gen_agent
    sections: list[SectionPayload] | None = None
    # wm_breakdown_agent
    breakdown: list[BreakdownItem] | None = None
    error_message: str | None = None
