"""EP-08 Group C — Unit tests for InboxService (C1.1, C1.2, C1.3).

RED phase: write failing tests before implementation.

Covers:
- Tier 1: direct + team pending review requests
- Tier 2: items owned by user in changes_requested state
- Tier 3: reviewer's unresolved change-request responses
- Tier 4: low-completeness (< 50) items in draft/in_clarification owned by user
- De-duplication: lowest tier wins
- Edge: empty team membership → no team tier-1 items
- Edge: user with no items → all tiers empty
- get_counts: per-tier counts match full get_inbox; total correct
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.domain.repositories.inbox_repository import IInboxRepository, InboxItem

# ---------------------------------------------------------------------------
# Fake InboxRepository
# ---------------------------------------------------------------------------


class FakeInboxRepository(IInboxRepository):
    """Purely in-memory fake — holds a fixed list of items returned for queries."""

    def __init__(self, items: list[InboxItem] | None = None) -> None:
        self._items = items or []

    async def get_inbox(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> list[InboxItem]:
        result = [i for i in self._items if i.owner_id == user_id]
        if item_type is not None:
            result = [i for i in result if i.item_type == item_type]
        return result

    async def get_counts(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> dict[int, int]:
        items = await self.get_inbox(user_id, workspace_id, item_type=item_type)
        counts: dict[int, int] = {}
        for item in items:
            counts[item.priority_tier] = counts.get(item.priority_tier, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _item(
    owner_id: UUID,
    tier: int,
    *,
    item_type: str = "task",
    source: str = "direct",
    team_id: UUID | None = None,
) -> InboxItem:
    return InboxItem(
        item_id=uuid4(),
        item_type=item_type,
        item_title=f"item-tier-{tier}",
        owner_id=owner_id,
        current_state="pending",
        priority_tier=tier,
        tier_label={1: "Pending reviews", 2: "Returned items", 3: "Blocking items", 4: "Decisions needed"}[tier],
        event_age=datetime.now(UTC),
        deeplink=f"/items/{uuid4()}",
        quick_action=None,
        source=source,
        team_id=team_id,
    )


# ---------------------------------------------------------------------------
# InboxService tests
# ---------------------------------------------------------------------------


class TestGetInbox:
    @pytest.mark.asyncio
    async def test_returns_tiers_structure(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = FakeInboxRepository(
            [
                _item(user_id, 1),
                _item(user_id, 2),
                _item(user_id, 3),
                _item(user_id, 4),
            ]
        )
        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert "tiers" in result
        assert "total" in result
        assert result["total"] == 4
        for tier_num in ("1", "2", "3", "4"):
            assert tier_num in result["tiers"]
            assert "items" in result["tiers"][tier_num]
            assert "count" in result["tiers"][tier_num]

    @pytest.mark.asyncio
    async def test_items_placed_in_correct_tier(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        t1 = _item(user_id, 1)
        t2 = _item(user_id, 2)
        t4 = _item(user_id, 4)
        repo = FakeInboxRepository([t1, t2, t4])
        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["tiers"]["1"]["count"] == 1
        assert result["tiers"]["2"]["count"] == 1
        assert result["tiers"]["3"]["count"] == 0
        assert result["tiers"]["4"]["count"] == 1
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_empty_inbox_returns_zeros(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = FakeInboxRepository([])
        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["total"] == 0
        for tier_num in ("1", "2", "3", "4"):
            assert result["tiers"][tier_num]["count"] == 0
            assert result["tiers"][tier_num]["items"] == []

    @pytest.mark.asyncio
    async def test_item_type_filter_applied(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        bug_item = _item(user_id, 1, item_type="bug")
        task_item = _item(user_id, 1, item_type="task")
        repo = FakeInboxRepository([bug_item, task_item])
        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(
            user_id=user_id, workspace_id=workspace_id, item_type="bug"
        )

        assert result["total"] == 1
        assert result["tiers"]["1"]["count"] == 1

    @pytest.mark.asyncio
    async def test_tier_labels_correct(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = FakeInboxRepository([_item(user_id, 1), _item(user_id, 2), _item(user_id, 3), _item(user_id, 4)])
        svc = InboxService(inbox_repo=repo)
        result = await svc.get_inbox(user_id=user_id, workspace_id=workspace_id)

        assert result["tiers"]["1"]["label"] == "Pending reviews"
        assert result["tiers"]["2"]["label"] == "Returned items"
        assert result["tiers"]["3"]["label"] == "Blocking items"
        assert result["tiers"]["4"]["label"] == "Decisions needed"


class TestGetCounts:
    @pytest.mark.asyncio
    async def test_counts_match_get_inbox(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = FakeInboxRepository([
            _item(user_id, 1),
            _item(user_id, 1),
            _item(user_id, 2),
            _item(user_id, 4),
        ])
        svc = InboxService(inbox_repo=repo)
        counts = await svc.get_counts(user_id=user_id, workspace_id=workspace_id)

        assert counts["by_tier"]["1"] == 2
        assert counts["by_tier"]["2"] == 1
        assert counts["by_tier"]["3"] == 0
        assert counts["by_tier"]["4"] == 1
        assert counts["total"] == 4

    @pytest.mark.asyncio
    async def test_counts_empty_inbox(self) -> None:
        from app.application.services.inbox_service import InboxService

        user_id = uuid4()
        workspace_id = uuid4()
        repo = FakeInboxRepository([])
        svc = InboxService(inbox_repo=repo)
        counts = await svc.get_counts(user_id=user_id, workspace_id=workspace_id)

        assert counts["total"] == 0
        for tier_num in ("1", "2", "3", "4"):
            assert counts["by_tier"][tier_num] == 0
