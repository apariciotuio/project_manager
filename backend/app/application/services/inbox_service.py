"""EP-08 Group C — InboxService.

Calls IInboxRepository.get_inbox() and shapes the result into the tiered
inbox response expected by the frontend.  NO SQL in this layer.

Tier labels (fixed by spec):
  1 — Pending reviews
  2 — Returned items
  3 — Blocking items
  4 — Decisions needed

EP-12 Group 3.2 — cache-aside via injected ICache.
  - Key:  inbox:{user_id}:{workspace_id}[:type={item_type}]
  - TTL:  30s per design.md
  - Invalidation: element status change affecting assignee (call invalidate())
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.domain.ports.cache import ICache
from app.domain.repositories.inbox_repository import IInboxRepository, InboxItem

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 30

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


def _cache_key(user_id: UUID, workspace_id: UUID, item_type: str | None) -> str:
    base = f"inbox:{user_id}:{workspace_id}"
    if item_type is None:
        return base
    return f"{base}:type={item_type}"


class InboxService:
    def __init__(
        self,
        *,
        inbox_repo: IInboxRepository,
        cache: ICache | None = None,
    ) -> None:
        self._inbox = inbox_repo
        self._cache = cache

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
        key = _cache_key(user_id, workspace_id, item_type)
        cached = await self._cache_get(key)
        if cached is not None:
            return cached

        items = await self._inbox.get_inbox(
            user_id, workspace_id, item_type=item_type
        )
        payload = self._shape(items)
        await self._cache_set(key, payload)
        return payload

    async def get_counts(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
        item_type: str | None = None,
    ) -> dict[str, Any]:
        """Return per-tier counts and total."""
        raw = await self._inbox.get_counts(
            user_id, workspace_id, item_type=item_type
        )
        by_tier = {str(tier): raw.get(tier, 0) for tier in _TIER_LABELS}
        total = sum(by_tier.values())
        return {"by_tier": by_tier, "total": total}

    async def invalidate(
        self,
        *,
        user_id: UUID,
        workspace_id: UUID,
    ) -> None:
        """Invalidate the inbox cache for a user/workspace.

        Call this from mutation paths that affect what appears in the inbox
        (element status change, review request created, etc.).
        Filtered variants (by item_type) are best-effort — the base key is
        always purged so the next fetch is a cache miss.
        """
        if self._cache is None:
            return
        key = _cache_key(user_id, workspace_id, None)
        try:
            await self._cache.delete(key)
        except Exception as exc:  # pragma: no cover — cache is best-effort
            logger.warning(
                "inbox_cache: invalidation failed for key=%s: %s", key, exc
            )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _shape(self, items: list[InboxItem]) -> dict[str, Any]:
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

    async def _cache_get(self, key: str) -> dict[str, Any] | None:
        if self._cache is None:
            return None
        try:
            raw = await self._cache.get(key)
        except Exception as exc:
            logger.warning("inbox_cache: get failed key=%s: %s", key, exc)
            return None
        if raw is None:
            return None
        try:
            decoded: dict[str, Any] = json.loads(raw)
        except ValueError as exc:
            logger.warning("inbox_cache: decode failed key=%s: %s", key, exc)
            return None
        return decoded

    async def _cache_set(self, key: str, payload: dict[str, Any]) -> None:
        if self._cache is None:
            return
        try:
            await self._cache.set(
                key, json.dumps(payload), _CACHE_TTL_SECONDS
            )
        except Exception as exc:
            logger.warning("inbox_cache: set failed key=%s: %s", key, exc)
