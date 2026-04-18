"""EP-13 — PuppetIngestRequest domain model.

Represents a single document-ingestion request sent (or to be sent) to Puppet.
State machine:
  queued → dispatched → succeeded
                      → failed (attempts < 3 → re-queued on retry)
                      → skipped (idempotent duplicate)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class PuppetIngestRequest:
    id: UUID
    workspace_id: UUID
    source_kind: str  # 'outbox' | 'manual' | 'webhook'
    work_item_id: UUID | None
    payload: dict[str, Any]
    status: str  # 'queued' | 'dispatched' | 'succeeded' | 'failed' | 'skipped'
    puppet_doc_id: str | None
    attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    succeeded_at: datetime | None

    # --- factory -----------------------------------------------------------

    @classmethod
    def create(
        cls,
        workspace_id: UUID,
        source_kind: str,
        work_item_id: UUID | None = None,
        payload: dict[str, Any] | None = None,
    ) -> PuppetIngestRequest:
        if source_kind not in ("outbox", "manual", "webhook"):
            raise ValueError(f"Invalid source_kind: {source_kind!r}")
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            workspace_id=workspace_id,
            source_kind=source_kind,
            work_item_id=work_item_id,
            payload=payload or {},
            status="queued",
            puppet_doc_id=None,
            attempts=0,
            last_error=None,
            created_at=now,
            updated_at=now,
            succeeded_at=None,
        )

    # --- state transitions -------------------------------------------------

    def mark_dispatched(self) -> None:
        """Called when the HTTP request to Puppet is about to be sent."""
        self.status = "dispatched"
        self.attempts += 1
        self.updated_at = datetime.now(UTC)

    def mark_succeeded(self, doc_id: str) -> None:
        now = datetime.now(UTC)
        self.status = "succeeded"
        self.puppet_doc_id = doc_id
        self.last_error = None
        self.succeeded_at = now
        self.updated_at = now

    def mark_failed(self, error: str) -> None:
        """Increments error count; caller decides whether to re-queue."""
        self.status = "failed"
        self.last_error = error[:500]
        self.updated_at = datetime.now(UTC)

    def mark_skipped(self, reason: str) -> None:
        self.status = "skipped"
        self.last_error = reason[:500]
        self.updated_at = datetime.now(UTC)

    def reset_for_retry(self) -> None:
        """Admin-triggered manual retry: reset to queued with 0 attempts."""
        self.status = "queued"
        self.attempts = 0
        self.last_error = None
        self.updated_at = datetime.now(UTC)
