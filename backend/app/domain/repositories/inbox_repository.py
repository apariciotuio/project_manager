"""EP-08 Group C — IInboxRepository interface.

SQL must NOT live in application services (backend_review.md LV-3).
All query logic lives in the infrastructure layer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class InboxItem:
    item_id: UUID
    item_type: str
    item_title: str
    owner_id: UUID
    current_state: str
    priority_tier: int
    tier_label: str
    event_age: datetime
    deeplink: str
    quick_action: dict[str, Any] | None
    source: str  # "direct" | "team"
    team_id: UUID | None


class IInboxRepository(ABC):
    @abstractmethod
    async def get_inbox(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> list[InboxItem]:
        """Return deduplicated inbox items across all four tiers.

        De-duplication: when an item appears in multiple tiers, only the
        lowest-numbered (highest-priority) tier is kept.  This is performed
        at the SQL level via ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY tier ASC).

        Filters:
          item_type — when provided, restrict results to that work-item type.
        """
        ...

    @abstractmethod
    async def get_counts(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> dict[int, int]:
        """Return per-tier item counts.

        Returns a dict keyed by tier number (1–4) with integer counts.
        Missing tiers default to 0 in the service layer.
        """
        ...
