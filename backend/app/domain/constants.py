"""Domain-level constants shared across application and domain layers."""

from __future__ import annotations

from uuid import UUID

# Sentinel actor ID used when the system itself triggers a state transition
# (e.g., auto-revert on content change). state_transitions.actor_id is nullable
# (migration 0010) so we pass None from the service; this constant is kept for
# documentation and any place that needs to identify system-origin transitions.
SYSTEM_ACTOR_ID: UUID | None = None

# Completeness threshold required before a work item can transition to READY
# without an override. EP-04 will implement the real scoring algorithm.
COMPLETENESS_READY_THRESHOLD: int = 80
