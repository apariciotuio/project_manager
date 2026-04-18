"""SSE channel registry — maps logical channel names to Postgres NOTIFY channel patterns.

Channel naming convention (canonical, all SSE consumers must use this):
  job:          sse:job:{job_id}
  conversation: sse:thread:{thread_id}
  user:         sse:user:{user_id}
  presence:     sse:presence:{workspace_id}

When workspace_id is provided at construction time, job channels gain a workspace
scope prefix (sse:ws:{workspace_id}:job:{job_id}) for multi-tenant isolation.
Other channel types embed their own scoping implicitly (thread_id / user_id are
globally unique UUIDs, so no additional workspace prefix is needed).
"""

from __future__ import annotations

from uuid import UUID


class ChannelRegistry:
    """Maps logical channel names to their Postgres NOTIFY channel strings."""

    def __init__(self, workspace_id: UUID | None = None) -> None:
        self._workspace_id = workspace_id

    # ------------------------------------------------------------------
    # Channel name builders
    # ------------------------------------------------------------------

    def job(self, job_id: str) -> str:
        """Postgres NOTIFY channel for an async job's progress stream."""
        if self._workspace_id is not None:
            return f"sse:ws:{self._workspace_id}:job:{job_id}"
        return f"sse:job:{job_id}"

    def conversation(self, thread_id: UUID) -> str:
        """Postgres NOTIFY channel for a conversation thread (EP-03 LLM streaming)."""
        return f"sse:thread:{thread_id}"

    def user_notifications(self, user_id: UUID) -> str:
        """Postgres NOTIFY channel for per-user real-time notifications (EP-08)."""
        return f"sse:user:{user_id}"

    def presence(self, workspace_id: UUID) -> str:
        """Postgres NOTIFY channel for workspace presence/online status."""
        return f"sse:presence:{workspace_id}"
