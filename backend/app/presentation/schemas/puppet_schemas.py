"""EP-13 — Pydantic schemas for Puppet callback + search + admin endpoints."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Puppet ingest callback (Puppet → our platform)
# ---------------------------------------------------------------------------


class PuppetCallbackRequest(BaseModel):
    """External webhook shape — kept lenient (extra ignored) so a future
    Puppet schema addition doesn't 422 our callback endpoint. HMAC auth
    is the primary trust gate here."""

    model_config = ConfigDict(extra="ignore")

    ingest_request_id: UUID
    status: str  # 'succeeded' | 'failed'
    puppet_doc_id: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Search proxy (our platform → Puppet search)
# ---------------------------------------------------------------------------


class PuppetSearchRequest(BaseModel):
    """FE-originated request — strict (unknown fields → 422)."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1)
    category: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class PuppetSearchHit(BaseModel):
    puppet_doc_id: str
    score: float
    snippet: str
    metadata: dict


# ---------------------------------------------------------------------------
# Admin: ingest requests list / retry
# ---------------------------------------------------------------------------


class PuppetIngestRequestResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    source_kind: str
    work_item_id: UUID | None
    status: str
    puppet_doc_id: str | None
    attempts: int
    last_error: str | None
    created_at: str
    updated_at: str
    succeeded_at: str | None
