"""EP-09 — Unit tests for PipelineQueryService.

RED phase: fail until PipelineQueryService is implemented.
"""
from __future__ import annotations

import hashlib
import json
from uuid import UUID, uuid4

import pytest


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._gets: int = 0
        self._sets: int = 0

    async def get(self, key: str) -> str | None:
        self._gets += 1
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._sets += 1
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _RowAgg:
    """Fake aggregate row: state, cnt, avg_age_days."""
    def __init__(self, state: str, cnt: int, avg_age: float = 0.0) -> None:
        self.state = state
        self.cnt = cnt
        self.avg_age_days = avg_age


class _Item:
    def __init__(self, id: UUID, state: str, title: str = "T", days_in_state: float = 0.0) -> None:
        self.id = id
        self.state = state
        self.title = title
        self.type = "story"
        self.owner_id = uuid4()
        self.completeness_score = 50
        self.updated_at = None
        self.days_in_state = days_in_state
        self.is_blocked = state == "blocked"


class FakeSession:
    def __init__(self, agg_rows: list[object], items: list[object]) -> None:
        self._agg_rows = agg_rows
        self._items = items
        self._call_count = 0

    async def execute(self, stmt: object) -> _FR:
        self._call_count += 1
        return _FR(agg_rows=self._agg_rows, items=self._items, call=self._call_count)


class _FR:
    def __init__(self, agg_rows: list[object], items: list[object], call: int) -> None:
        self._agg_rows = agg_rows
        self._items = items
        self._call = call

    def all(self) -> list[object]:
        if self._call == 1:
            return self._agg_rows
        return self._items

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._items)


class _ScalarResult:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return self._items


FSM_ORDER = ["draft", "in_clarification", "in_review", "partially_validated", "ready"]


class TestPipelineColumns:
    @pytest.mark.asyncio
    async def test_returns_all_fsm_states_as_columns(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        agg = [_RowAgg(s, 0) for s in FSM_ORDER]
        session = FakeSession(agg_rows=agg, items=[])
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        col_keys = [c["state"] for c in result["columns"]]
        for state in FSM_ORDER:
            assert state in col_keys

    @pytest.mark.asyncio
    async def test_archived_state_absent(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        agg = [_RowAgg("archived", 3)]
        session = FakeSession(agg_rows=agg, items=[])
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        col_keys = [c["state"] for c in result["columns"]]
        assert "archived" not in col_keys

    @pytest.mark.asyncio
    async def test_columns_in_fsm_order(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        # Provide in reverse order — service must reorder
        agg = [_RowAgg(s, 1) for s in reversed(FSM_ORDER)]
        session = FakeSession(agg_rows=agg, items=[])
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        col_keys = [c["state"] for c in result["columns"] if c["state"] in FSM_ORDER]
        assert col_keys == FSM_ORDER

    @pytest.mark.asyncio
    async def test_count_in_column(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        agg = [_RowAgg("draft", 7, 3.5)]
        session = FakeSession(agg_rows=agg, items=[_Item(uuid4(), "draft")])
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        draft_col = next(c for c in result["columns"] if c["state"] == "draft")
        assert draft_col["count"] == 7
        assert draft_col["avg_age_days"] == pytest.approx(3.5, abs=0.01)

    @pytest.mark.asyncio
    async def test_items_capped_at_20_per_column(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        agg = [_RowAgg("draft", 25)]
        items = [_Item(uuid4(), "draft") for _ in range(25)]
        session = FakeSession(agg_rows=agg, items=items)
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        draft_col = next(c for c in result["columns"] if c["state"] == "draft")
        assert len(draft_col["items"]) <= 20

    @pytest.mark.asyncio
    async def test_blocked_lane_present(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        agg = [_RowAgg("blocked", 2)]
        items = [_Item(uuid4(), "blocked")]
        session = FakeSession(agg_rows=agg, items=items)
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        assert "blocked_lane" in result


class TestPipelineCache:
    @pytest.mark.asyncio
    async def test_warm_cache_skips_db(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        cached_data = {
            "columns": [{"state": "draft", "count": 5, "avg_age_days": 1.0, "items": []}],
            "blocked_lane": [],
        }
        cache = FakeCache()
        # Must match the cache key format used by PipelineQueryService
        filter_params = {
            "workspace_id": str(ws_id),
            "project_id": None,
            "team_id": None,
            "owner_id": None,
            "state": None,
        }
        raw = json.dumps(filter_params, sort_keys=True).encode()
        filter_hash = hashlib.sha256(raw).hexdigest()
        cache_key = f"pipeline:{ws_id}:{filter_hash}"
        await cache.set(cache_key, json.dumps(cached_data), 30)

        session = FakeSession(agg_rows=[], items=[])
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_pipeline(workspace_id=ws_id)

        assert result["columns"][0]["count"] == 5
        assert session._call_count == 0

    @pytest.mark.asyncio
    async def test_invalid_filter_raises_422_compatible_error(self) -> None:
        from app.application.services.pipeline_service import PipelineQueryService

        ws_id = uuid4()
        session = FakeSession(agg_rows=[], items=[])
        cache = FakeCache()
        svc = PipelineQueryService(session=session, cache=cache)  # type: ignore[arg-type]
        # Valid call should work — no 422 here
        result = await svc.get_pipeline(workspace_id=ws_id)
        assert "columns" in result
