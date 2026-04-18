"""Unit tests for PgRateLimiter.

Uses a fake AsyncSession — no real DB, no network.  The fake simulates the
RETURNING clause by tracking per-(identifier, minute) counts in memory.

Scenarios:
  - First call in new window → allowed=True, count=1, remaining=limit-1
  - Subsequent calls under limit → allowed=True, count increments
  - Call that pushes count over limit → allowed=False, remaining=0
  - DB error → fail-open: allowed=True, logs WARNING
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import pytest

from app.infrastructure.rate_limiting.pg_rate_limiter import PgRateLimiter

# ---------------------------------------------------------------------------
# Fake AsyncSession
# ---------------------------------------------------------------------------

_WINDOW_START = datetime(2026, 4, 18, 10, 5, 0, tzinfo=UTC)


class _FakeRow:
    def __init__(self, count: int, window_start_minute: datetime) -> None:
        self.count = count
        self.window_start_minute = window_start_minute


class _FakeResult:
    def __init__(self, row: _FakeRow | None) -> None:
        self._row = row

    def fetchone(self) -> _FakeRow | None:
        return self._row


class FakeSession:
    """In-memory stand-in for AsyncSession.

    Simulates the upsert: first call per identifier returns count=1, each
    subsequent call increments it.
    """

    def __init__(self) -> None:
        self._buckets: dict[str, int] = {}

    async def execute(self, statement: Any, params: dict | None = None) -> _FakeResult:
        identifier = (params or {}).get("identifier", "")
        self._buckets[identifier] = self._buckets.get(identifier, 0) + 1
        count = self._buckets[identifier]
        return _FakeResult(_FakeRow(count=count, window_start_minute=_WINDOW_START))


class BrokenSession:
    """AsyncSession that always raises to simulate DB failure."""

    async def execute(self, statement: Any, params: dict | None = None) -> Any:
        raise RuntimeError("connection refused")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_call_in_new_window_is_allowed() -> None:
    """First request in an empty window: count=1, allowed, remaining=limit-1."""
    limiter = PgRateLimiter(FakeSession())
    result = await limiter.check("ip:1.2.3.4", limit=5)

    assert result.allowed is True
    assert result.count == 1
    assert result.remaining == 4
    assert result.limit == 5


@pytest.mark.asyncio
async def test_under_limit_remains_allowed() -> None:
    """Calls up to the limit all return allowed=True."""
    session = FakeSession()
    limiter = PgRateLimiter(session)
    limit = 3

    for expected_count in range(1, limit + 1):
        result = await limiter.check("user:abc", limit=limit)
        assert result.allowed is True
        assert result.count == expected_count


@pytest.mark.asyncio
async def test_over_limit_is_denied() -> None:
    """First call beyond the limit returns allowed=False, remaining=0."""
    session = FakeSession()
    limiter = PgRateLimiter(session)
    limit = 2

    # Exhaust the limit
    for _ in range(limit):
        await limiter.check("ip:over", limit=limit)

    # This is the (limit+1)th call
    result = await limiter.check("ip:over", limit=limit)
    assert result.allowed is False
    assert result.remaining == 0


@pytest.mark.asyncio
async def test_reset_at_is_next_minute() -> None:
    """reset_at must equal window_start + 60 seconds."""
    limiter = PgRateLimiter(FakeSession())
    result = await limiter.check("ip:reset", limit=10)

    expected_reset = int(_WINDOW_START.timestamp()) + 60
    assert result.reset_at == expected_reset


@pytest.mark.asyncio
async def test_db_error_fails_open(caplog: pytest.LogCaptureFixture) -> None:
    """DB failure → request is allowed (fail-open), WARNING is logged."""
    limiter = PgRateLimiter(BrokenSession())

    with caplog.at_level(
        logging.WARNING, logger="backend.app.infrastructure.rate_limiting.pg_rate_limiter"
    ):
        result = await limiter.check("ip:broken", limit=10)

    assert result.allowed is True
    assert any("failing open" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_db_error_remaining_is_non_negative(caplog: pytest.LogCaptureFixture) -> None:
    """Fail-open result must have count=0 and remaining=limit."""
    limiter = PgRateLimiter(BrokenSession())

    with caplog.at_level(logging.WARNING):
        result = await limiter.check("ip:broken2", limit=7)

    assert result.count == 0
    assert result.remaining == 7


@pytest.mark.asyncio
async def test_different_identifiers_are_independent() -> None:
    """Each identifier gets its own counter — no cross-contamination."""
    session = FakeSession()
    limiter = PgRateLimiter(session)

    await limiter.check("user:alice", limit=5)
    await limiter.check("user:alice", limit=5)
    result_bob = await limiter.check("user:bob", limit=5)

    assert result_bob.count == 1  # Bob's first call, regardless of Alice's
