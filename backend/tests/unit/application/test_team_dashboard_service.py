"""EP-09 — Unit tests for TeamDashboardService.

RED phase: fail until TeamDashboardService is implemented.
"""
from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class _Row:
    def __init__(self, **kw: object) -> None:
        for k, v in kw.items():
            setattr(self, k, v)


class FakeSession:
    def __init__(
        self,
        state_rows: list[object],
        review_count: int,
        velocity: int,
        blocked_count: int,
    ) -> None:
        self._state_rows = state_rows
        self._review_count = review_count
        self._velocity = velocity
        self._blocked_count = blocked_count
        self._call_count = 0

    async def execute(self, stmt: object) -> "_FR":
        self._call_count += 1
        return _FR(
            rows=self._state_rows,
            scalars=[self._review_count, self._velocity, self._blocked_count],
            call=self._call_count,
        )


class _FR:
    def __init__(self, rows: list[object], scalars: list[int], call: int) -> None:
        self._rows = rows
        self._scalars = scalars
        self._call = call

    def all(self) -> list[object]:
        return self._rows

    def scalar(self) -> int:
        idx = self._call - 2  # call 1 = state_rows, calls 2+ = scalars
        if 0 <= idx < len(self._scalars):
            return self._scalars[idx]
        return 0

    def scalar_one_or_none(self) -> int | None:
        return self.scalar()


class TestTeamDashboardColdCache:
    @pytest.mark.asyncio
    async def test_returns_owned_by_state(self) -> None:
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        rows = [_Row(state="draft", cnt=5), _Row(state="in_review", cnt=2)]
        session = FakeSession(state_rows=rows, review_count=3, velocity=10, blocked_count=1)
        cache = FakeCache()
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["owned_by_state"]["draft"] == 5
        assert result["owned_by_state"]["in_review"] == 2

    @pytest.mark.asyncio
    async def test_returns_pending_reviews_count(self) -> None:
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=7, velocity=0, blocked_count=0)
        cache = FakeCache()
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["pending_reviews"] == 7

    @pytest.mark.asyncio
    async def test_returns_blocked_count(self) -> None:
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=0, velocity=0, blocked_count=4)
        cache = FakeCache()
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["blocked_count"] == 4

    @pytest.mark.asyncio
    async def test_returns_recent_ready_items(self) -> None:
        """SF-4: field renamed from velocity_last_30d to recent_ready_items — approximate metric."""
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=0, velocity=15, blocked_count=0)
        cache = FakeCache()
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["recent_ready_items"] == 15
        assert "velocity_last_30d" not in result, "old field name must be gone"

    @pytest.mark.asyncio
    async def test_empty_team_returns_zeros(self) -> None:
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=0, velocity=0, blocked_count=0)
        cache = FakeCache()
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["owned_by_state"] == {}
        assert result["blocked_count"] == 0
        assert result["recent_ready_items"] == 0


class TestTeamDashboardCache:
    @pytest.mark.asyncio
    async def test_warm_cache_skips_db(self) -> None:
        from app.application.services.team_dashboard_service import TeamDashboardService

        team_id = uuid4()
        ws_id = uuid4()
        cached_data = {
            "owned_by_state": {"ready": 3},
            "pending_reviews": 0,
            "blocked_count": 0,
            "velocity_last_30d": 8,
        }
        cache = FakeCache()
        await cache.set(f"dashboard:team:{team_id}", json.dumps(cached_data), 120)

        session = FakeSession(state_rows=[], review_count=0, velocity=0, blocked_count=0)
        svc = TeamDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(team_id, workspace_id=ws_id)

        assert result["owned_by_state"]["ready"] == 3
        assert result["velocity_last_30d"] == 8
        assert session._call_count == 0
