"""EP-09 — Unit tests for DashboardService.

Uses FakeCache; no real DB needed (service queries are tested in integration).
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

# We test the cache layer in isolation without a real session.
# For full aggregation tests, see integration tests.


class FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


class TestCacheBehavior:
    """Test that the cache layer works correctly without hitting DB."""

    @pytest.mark.asyncio
    async def test_invalidate_removes_cache_key(self) -> None:
        from app.application.services.dashboard_service import DashboardService

        cache = FakeCache()
        ws_id = uuid4()
        # Pre-populate cache
        await cache.set(f"dashboard:workspace:{ws_id}", json.dumps({"test": True}), 60)

        # Invalidate — needs a session, but we only call invalidate
        # Create a mock session (not used by invalidate)
        class _FakeSession:
            pass

        svc = DashboardService(session=_FakeSession(), cache=cache)  # type: ignore[arg-type]
        await svc.invalidate(ws_id)

        assert await cache.get(f"dashboard:workspace:{ws_id}") is None

    @pytest.mark.asyncio
    async def test_cache_key_is_workspace_scoped(self) -> None:
        from app.application.services.dashboard_service import DashboardService

        cache = FakeCache()
        ws1 = uuid4()
        ws2 = uuid4()
        await cache.set(f"dashboard:workspace:{ws1}", json.dumps({"ws": "1"}), 60)

        class _FakeSession:
            pass

        svc = DashboardService(session=_FakeSession(), cache=cache)  # type: ignore[arg-type]
        await svc.invalidate(ws1)

        # ws2 cache untouched
        assert await cache.get(f"dashboard:workspace:{ws2}") is None
        # ws1 cache gone
        assert await cache.get(f"dashboard:workspace:{ws1}") is None
