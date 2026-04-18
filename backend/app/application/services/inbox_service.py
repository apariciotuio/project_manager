"""EP-08 Group C — InboxService.

Calls IInboxRepository.get_inbox() and shapes the result into the tiered
inbox response expected by the frontend.  NO SQL in this layer.

Tier labels (fixed by spec):
  1 — Pending reviews
  2 — Returned items
  3 — Blocking items
  4 — Decisions needed
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.repositories.inbox_repository import IInboxRepository, InboxItem

_TIER_LABELS: dict[int, str] = {
    1: "Pending reviews",
    2: "Returned items",
    3: "Blocking items",
    4: "Decisions needed",
}


def _item_payload(item: InboxItem) -> dict[str, Any]:
    return {
        "item_id": str(item.item_id),
        "item_type": item.item_type,
        "item_title": item.item_title,
        "owner_id": str(item.owner_id),
        "current_state": item.current_state,
        "priority_tier": item.priority_tier,
        "tier_label": item.tier_label,
        "event_age": item.event_age.isoformat(),
        "deeplink": item.deeplink,
        "quick_action": item.quick_action,
        "source": item.source,
        "team_id": str(item.team_id) if item.team_id else None,
    }


class InboxService:
    def __init__(self, *, inbox_repo: IInboxRepository) -> None:
        self._inbox = inbox_repo

    async def get_inbox(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        item_type: str | None = None,
    ) -> dict[str, Any]:
        """Return the tiered inbox structure for a user.

        Returns:
            {
                "tiers": {
                    "1": {"label": "...", "items": [...], "count": N},
                    ...
                },
                "total": N
            }
        """
        items = await self._inbox.get_inbox(user_id, workspace_id, item_type=item_type)

        tiers: dict[str, dict[str, Any]] = {
            str(tier): {"label": label, "items": [], "count": 0}
            for tier, label in _TIER_LABELS.items()
        }

        for item in items:
            key = str(item.priority_tier)
            if key in tiers:
                tiers[key]["items"].append(_item_payload(item))
                tiers[key]["count"] += 1

        total = sum(t["count"] for t in tiers.values())
        return {"tiers": tiers, "total": total}

    async def get_counts(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        item_type: str | None = None,
    ) -> dict[str, Any]:
        """Return per-tier counts and total."""
        raw = await self._inbox.get_counts(user_id, workspace_id, item_type=item_type)
        by_tier = {str(tier): raw.get(tier, 0) for tier in _TIER_LABELS}
        total = sum(by_tier.values())
        return {"by_tier": by_tier, "total": total}
