"""EP-07 Phase 3 — TimelineService unit tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.services.timeline_service import TimelineService
from app.domain.models.timeline_event import TimelineActorType, TimelineEvent
from app.domain.repositories.timeline_repository import ITimelineEventRepository


class FakeTimelineRepo(ITimelineEventRepository):
    def __init__(self) -> None:
        self._events: list[TimelineEvent] = []

    async def insert(self, event: TimelineEvent) -> TimelineEvent:
        self._events.append(event)
        return event

    async def list_for_work_item(
        self,
        work_item_id: UUID,
        *,
        before_occurred_at: datetime | None = None,
        before_id: UUID | None = None,
        limit: int = 50,
        event_types: list[str] | None = None,
        actor_types: list[str] | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[TimelineEvent]:
        results = [e for e in self._events if e.work_item_id == work_item_id]

        if event_types:
            results = [e for e in results if e.event_type in event_types]
        if actor_types:
            results = [e for e in results if e.actor_type.value in actor_types]
        if from_date:
            results = [e for e in results if e.occurred_at >= from_date]
        if to_date:
            results = [e for e in results if e.occurred_at <= to_date]
        if before_occurred_at is not None and before_id is not None:
            results = [
                e for e in results
                if e.occurred_at < before_occurred_at
                or (e.occurred_at == before_occurred_at and e.id < before_id)
            ]

        results.sort(key=lambda e: (e.occurred_at, e.id), reverse=True)
        return results[:limit]


def _event(
    work_item_id: UUID,
    workspace_id: UUID,
    event_type: str = "state_transition",
    actor_type: TimelineActorType = TimelineActorType.HUMAN,
    occurred_at: datetime | None = None,
) -> TimelineEvent:
    if occurred_at is None:
        occurred_at = datetime.now(UTC)
    return TimelineEvent(
        id=uuid4(),
        work_item_id=work_item_id,
        workspace_id=workspace_id,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=None,
        actor_display_name=None,
        summary="test event",
        payload={},
        occurred_at=occurred_at,
        source_id=None,
        source_table=None,
    )


class TestTimelineService:
    @pytest.mark.asyncio
    async def test_list_reverse_chronological(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()
        now = datetime.now(UTC)

        for i in range(5):
            await repo.insert(_event(wid, ws, occurred_at=now + timedelta(seconds=i)))

        result = await svc.list_events(work_item_id=wid, workspace_id=ws)
        times = [e.occurred_at for e in result["events"]]
        assert times == sorted(times, reverse=True)

    @pytest.mark.asyncio
    async def test_event_type_filter(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()

        await repo.insert(_event(wid, ws, event_type="state_transition"))
        await repo.insert(_event(wid, ws, event_type="comment_added"))

        result = await svc.list_events(work_item_id=wid, workspace_id=ws, event_types=["state_transition"])
        assert all(e.event_type == "state_transition" for e in result["events"])

    @pytest.mark.asyncio
    async def test_actor_type_filter(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()

        await repo.insert(_event(wid, ws, actor_type=TimelineActorType.HUMAN))
        await repo.insert(_event(wid, ws, actor_type=TimelineActorType.SYSTEM))

        result = await svc.list_events(work_item_id=wid, workspace_id=ws, actor_types=["system"])
        assert all(e.actor_type == TimelineActorType.SYSTEM for e in result["events"])

    @pytest.mark.asyncio
    async def test_has_more_false_on_last_page(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()

        await repo.insert(_event(wid, ws))
        await repo.insert(_event(wid, ws))

        result = await svc.list_events(work_item_id=wid, workspace_id=ws, limit=10)
        assert result["has_more"] is False
        assert result["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_has_more_true_when_more_pages(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()
        now = datetime.now(UTC)

        for i in range(5):
            await repo.insert(_event(wid, ws, occurred_at=now + timedelta(seconds=i)))

        result = await svc.list_events(work_item_id=wid, workspace_id=ws, limit=3)
        assert result["has_more"] is True
        assert result["next_cursor"] is not None

    @pytest.mark.asyncio
    async def test_cursor_pagination_non_overlapping(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()
        now = datetime.now(UTC)

        for i in range(6):
            await repo.insert(_event(wid, ws, occurred_at=now + timedelta(seconds=i)))

        page1 = await svc.list_events(work_item_id=wid, workspace_id=ws, limit=3)
        assert len(page1["events"]) == 3
        assert page1["has_more"] is True

        page2 = await svc.list_events(
            work_item_id=wid, workspace_id=ws, limit=3, cursor=page1["next_cursor"]
        )
        page1_ids = {e.id for e in page1["events"]}
        page2_ids = {e.id for e in page2["events"]}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_append_event(self) -> None:
        repo = FakeTimelineRepo()
        svc = TimelineService(timeline_repo=repo)
        wid = uuid4()
        ws = uuid4()

        await svc.append(
            work_item_id=wid,
            workspace_id=ws,
            event_type="state_transition",
            actor_type=TimelineActorType.HUMAN,
            actor_id=uuid4(),
            summary="state changed",
            payload={"from": "draft", "to": "ready"},
        )
        assert len(repo._events) == 1
        assert repo._events[0].event_type == "state_transition"
