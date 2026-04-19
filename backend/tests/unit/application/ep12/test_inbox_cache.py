"""EP-12 Group 3.2 — InboxService cache-aside wiring.

Spec (design.md cache key table):
  - Key:  inbox:{user_id}:{workspace_id}
  - TTL:  30s
  - Invalidation trigger: element status change affecting assignee

Tests cover:
  - Cache miss -> repo called -> result cached
  - Cache hit  -> repo NOT called, cached payload returned
  - Cache key format matches the non-negotiable spec
  - Explicit invalidation deletes the key
  - item_type filter yields distinct keys (so a filtered view does not poison the unfiltered cache)
  - Unavailable cache (get raises) degrades gracefully to DB (no 5xx)
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.repositories.inbox_repository import IInboxRepository, InboxItem
from tests.fakes.fake_repositories import FakeCache

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class CountingInboxRepository(IInboxRepository):
    """Tracks call counts to prove cache hit skips the DB."""

    def __init__(self, items: list[InboxItem] | None = None) -> None:
        self._items = items or []
        self.get_inbox_calls: int = 0
        self.get_counts_calls: int = 0

    async def get_inbox(
        self,
        user_id: UUID,
        workspace_id: UUID,  # noqa: ARG002 — interface signature
        *,
        item_type: str | None = None,
    ) -> list[InboxItem]:
        self.get_inbox_calls += 1
        result = [i for i in self._items if i.owner_id == user_id]
        if item_type is not None:
            result = [i for i in result if i.item_type == item_type]
        return result

    async def get_counts(
        self,
        user_id: UUID,
        workspace_id: UUID,  # noqa: ARG002 — interface signature
        *,
        item_type: str | None = None,
    ) -> dict[int, int]:
        self.get_counts_calls += 1
        items = [i for i in self._items if i.owner_id == user_id]
        if item_type is not None:
            items = [i for i in items if i.item_type == item_type]
        counts: dict[int, int] = {}
        for item in items:
            counts[item.priority_tier] = counts.get(item.priority_tier, 0) + 1
        return counts


class RaisingCache:
    """ICache whose every call raises — simulates backend unavailability."""

    def __init__(
        self,
        *,
        on_get: bool = True,
        on_set: bool = False,
        on_delete: bool = False,
    ) -> None:
        self._on_get = on_get
        self._on_set = on_set
        self._on_delete = on_delete

    async def get(self, key: str) -> str | None:  # noqa: ARG002
        if self._on_get:
            raise ConnectionError("cache backend unreachable")
        return None

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:  # noqa: ARG002
        if self._on_set:
            raise TimeoutError("cache backend slow")

    async def delete(self, key: str) -> None:  # noqa: ARG002
        if self._on_delete:
            raise OSError("cache backend down")


_TIER_LABELS = {
    1: "Pending reviews",
    2: "Returned items",
    3: "Blocking items",
    4: "Decisions needed",
}


def _item(owner_id: UUID, tier: int, *, item_type: str = "task") -> InboxItem:
    return InboxItem(
        item_id=uuid4(),
        item_type=item_type,
        item_title=f"item-tier-{tier}",
        owner_id=owner_id,
        current_state="pending",
        priority_tier=tier,
        tier_label=_TIER_LABELS[tier],
        event_age=datetime.now(UTC),
        deeplink=f"/items/{uuid4()}",
        quick_action=None,
        source="direct",
        team_id=None,
    )


# ---------------------------------------------------------------------------
# Cache-aside contract
# ---------------------------------------------------------------------------


class TestInboxCacheAside:
    @pytest.mark.asyncio
    async def test_miss_populates_cache_and_calls_repo(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1), _item(user_id, 2)])
        cache = FakeCache()

        svc = InboxService(inbox_repo=repo, cache=cache)
        first = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert first["total"] == 2
        assert repo.get_inbox_calls == 1
        assert cache.set_call_count == 1

    @pytest.mark.asyncio
    async def test_hit_skips_repo(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = FakeCache()

        svc = InboxService(inbox_repo=repo, cache=cache)
        await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)
        first_calls = repo.get_inbox_calls
        second = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert repo.get_inbox_calls == first_calls, "warm cache should not hit the repo"
        assert second["total"] == 1

    @pytest.mark.asyncio
    async def test_cache_key_matches_spec(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = UUID("11111111-1111-1111-1111-111111111111")
        workspace_id = UUID("22222222-2222-2222-2222-222222222222")
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = FakeCache()

        svc = InboxService(inbox_repo=repo, cache=cache)
        await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        expected_key = f"inbox:{user_id}:{workspace_id}"
        assert expected_key in cache._store, (
            f"expected cache key {expected_key}, got {list(cache._store.keys())}"
        )

    @pytest.mark.asyncio
    async def test_item_type_filter_yields_distinct_key(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository(
            [_item(user_id, 1, item_type="task"), _item(user_id, 1, item_type="bug")]
        )
        cache = FakeCache()

        svc = InboxService(inbox_repo=repo, cache=cache)
        unfiltered = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)
        filtered = await svc.get_inbox(
            user_id=user_id, workspace_id=workspace_id, item_type="bug"
        )

        assert unfiltered["total"] == 2
        assert filtered["total"] == 1
        assert len(cache._store) == 2, "filter must produce a distinct cache entry"

    @pytest.mark.asyncio
    async def test_invalidate_deletes_key(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = FakeCache()

        svc = InboxService(inbox_repo=repo, cache=cache)
        await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)
        assert cache.set_call_count == 1
        assert len(cache._store) == 1

        await svc.invalidate(user_id=user_id, workspace_id=workspace_id)

        assert cache.delete_call_count >= 1
        await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)
        assert repo.get_inbox_calls == 2, "invalidated cache must force a repo fetch"

    @pytest.mark.asyncio
    async def test_cache_get_unavailable_falls_back_to_db(self) -> None:
        """Per design: cache errors must NOT propagate as HTTP 5xx."""
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = RaisingCache(on_get=True)

        svc = InboxService(inbox_repo=repo, cache=cache)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["total"] == 1
        assert repo.get_inbox_calls == 1

    @pytest.mark.asyncio
    async def test_cache_set_unavailable_still_returns_data(self) -> None:
        """If cache write fails after a DB fetch, the request still succeeds."""
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = RaisingCache(on_get=False, on_set=True)

        svc = InboxService(inbox_repo=repo, cache=cache)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["total"] == 1
        assert repo.get_inbox_calls == 1

    @pytest.mark.asyncio
    async def test_invalidate_unavailable_is_silent(self) -> None:
        """Invalidation failure must not raise into the mutation path."""
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])
        cache = RaisingCache(on_get=False, on_delete=True)

        svc = InboxService(inbox_repo=repo, cache=cache)
        await svc.invalidate(user_id=user_id, workspace_id=workspace_id)

    @pytest.mark.asyncio
    async def test_service_without_cache_still_works(self) -> None:
        """InboxService must remain usable without a cache (dev / migration path)."""
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = CountingInboxRepository([_item(user_id, 1)])

        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["total"] == 1
        assert repo.get_inbox_calls == 1
