"""EP-09 — Unit tests for PersonDashboardService.

RED phase: fail until PersonDashboardService is implemented.
Uses fake session + fake cache — no DB required.
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


class FakeSession:
    """Fake session that returns canned scalar results per query."""

    def __init__(self, state_rows: list[object], review_count: int, notification_count: int) -> None:
        self._state_rows = state_rows
        self._review_count = review_count
        self._notification_count = notification_count
        self._call_count = 0

    async def execute(self, stmt: object) -> "_FakeResult":
        self._call_count += 1
        return _FakeResult(
            state_rows=self._state_rows,
            scalar_value=(
                self._review_count if self._call_count == 2 else self._notification_count
            ),
        )


class _Row:
    def __init__(self, state: str, cnt: int) -> None:
        self.state = state
        self.cnt = cnt


class _FakeResult:
    def __init__(self, state_rows: list[object], scalar_value: int) -> None:
        self._rows = state_rows
        self._scalar = scalar_value

    def all(self) -> list[object]:
        return self._rows

    def scalar(self) -> int:
        return self._scalar

    def scalar_one_or_none(self) -> int | None:
        return self._scalar


class TestPersonDashboardColdCache:
    @pytest.mark.asyncio
    async def test_returns_owned_by_state(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        rows = [_Row("draft", 3), _Row("in_review", 1)]
        session = FakeSession(state_rows=rows, review_count=2, notification_count=5)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["owned_by_state"]["draft"] == 3
        assert result["owned_by_state"]["in_review"] == 1

    @pytest.mark.asyncio
    async def test_returns_pending_reviews_count(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=4, notification_count=0)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["pending_reviews_count"] == 4

    @pytest.mark.asyncio
    async def test_returns_inbox_count(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=0, notification_count=7)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["inbox_count"] == 7

    @pytest.mark.asyncio
    async def test_overloaded_flag_set_when_many_in_clarification(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        rows = [_Row("in_clarification", 6)]
        session = FakeSession(state_rows=rows, review_count=0, notification_count=0)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["overloaded"] is True

    @pytest.mark.asyncio
    async def test_overloaded_flag_false_when_few_in_clarification(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        rows = [_Row("in_clarification", 5)]
        session = FakeSession(state_rows=rows, review_count=0, notification_count=0)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["overloaded"] is False

    @pytest.mark.asyncio
    async def test_zero_state_returns_empty_owned_by_state(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        session = FakeSession(state_rows=[], review_count=0, notification_count=0)
        cache = FakeCache()
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["owned_by_state"] == {}
        assert result["overloaded"] is False


class TestPersonDashboardCache:
    @pytest.mark.asyncio
    async def test_warm_cache_returns_cached_result(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid = uuid4()
        ws_id = uuid4()
        cached_data = {"owned_by_state": {"draft": 99}, "overloaded": False, "inbox_count": 0, "pending_reviews_count": 0}
        cache = FakeCache()
        await cache.set(f"dashboard:person:{uid}", json.dumps(cached_data), 120)

        session = FakeSession(state_rows=[], review_count=0, notification_count=0)
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid, workspace_id=ws_id)

        assert result["owned_by_state"]["draft"] == 99
        # Session was not called (no DB hit)
        assert session._call_count == 0

    @pytest.mark.asyncio
    async def test_cache_key_is_user_scoped(self) -> None:
        from app.application.services.person_dashboard_service import PersonDashboardService

        uid1 = uuid4()
        uid2 = uuid4()
        ws_id = uuid4()
        cached_data = {"owned_by_state": {"draft": 5}, "overloaded": False, "inbox_count": 0, "pending_reviews_count": 0}
        cache = FakeCache()
        await cache.set(f"dashboard:person:{uid1}", json.dumps(cached_data), 120)

        # uid2 should not get uid1's data
        session = FakeSession(state_rows=[], review_count=0, notification_count=0)
        svc = PersonDashboardService(session=session, cache=cache)  # type: ignore[arg-type]
        result = await svc.get_metrics(uid2, workspace_id=ws_id)

        assert result["owned_by_state"] == {}
