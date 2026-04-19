"""Unit tests for SSE infrastructure — PgNotificationBus + JobProgressService.

Tests:
  PgNotificationBus:
    - publish() calls pg_notify with JSON-encoded payload
    - publish() includes channel in payload
    - publish() raises PayloadTooLarge when payload > 8000 bytes
    - subscribe() yields incoming messages via queue
    - subscribe() calls UNLISTEN and releases connection on generator close

  JobProgressService (in-memory):
    - set_state / get_state roundtrip
    - get_state returns None when missing
    - complete sets done state with message_id
    - fail sets error state
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.sse.job_progress_service import JobProgressService, JobState
from app.infrastructure.sse.pg_notification_bus import PayloadTooLarge, PgNotificationBus

# ---------------------------------------------------------------------------
# Fake asyncpg connection for unit tests
# ---------------------------------------------------------------------------


class FakeAsyncpgConnection:
    """Minimal asyncpg.Connection stand-in that records calls."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, ...]] = []
        self._listeners: dict[str, Any] = {}
        self._notify_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def execute(self, sql: str, *args: Any) -> None:
        self.executed.append((sql, *args))

    async def add_listener(self, channel: str, callback: Any) -> None:
        self._listeners[channel] = callback

    async def remove_listener(self, channel: str, callback: Any) -> None:
        self._listeners.pop(channel, None)

    async def close(self) -> None:
        pass

    def inject_notify(self, channel: str, payload: str) -> None:
        """Simulate Postgres firing NOTIFY — call the registered listener."""
        cb = self._listeners.get(channel)
        if cb is not None:
            cb(self, 0, channel, payload)


# ---------------------------------------------------------------------------
# Helpers to build a bus backed by a fake connection
# ---------------------------------------------------------------------------


def _make_bus_with_fake_conn(
    fake_conn: FakeAsyncpgConnection,
) -> PgNotificationBus:
    bus = PgNotificationBus(dsn="postgresql://fake/fake")
    # Patch both pooled and dedicated acquire/release to return the fake conn
    bus._acquire_pooled = AsyncMock(return_value=fake_conn)  # type: ignore[method-assign]
    bus._release_pooled = AsyncMock()  # type: ignore[method-assign]
    bus._acquire_dedicated = AsyncMock(return_value=fake_conn)  # type: ignore[method-assign]
    bus._release_dedicated = AsyncMock()  # type: ignore[method-assign]
    return bus


# ---------------------------------------------------------------------------
# PgNotificationBus — publish() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pg_bus_publish_calls_pg_notify_with_json() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    await bus.publish("sse:thread:abc", {"type": "token", "payload": {"text": "hello"}})

    assert len(fake.executed) == 1
    sql, channel_arg, payload_arg = fake.executed[0]
    assert "pg_notify" in sql
    assert channel_arg == "sse:thread:abc"
    decoded = json.loads(payload_arg)
    assert decoded["type"] == "token"
    assert decoded["payload"]["text"] == "hello"


@pytest.mark.asyncio
async def test_pg_bus_publish_includes_channel_in_payload() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    await bus.publish("sse:user:xyz", {"type": "notify", "payload": {}})

    _, _, payload_arg = fake.executed[0]
    decoded = json.loads(payload_arg)
    assert decoded["channel"] == "sse:user:xyz"


@pytest.mark.asyncio
async def test_pg_bus_publish_raises_payload_too_large() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    big_message = {"type": "data", "payload": {"x": "A" * 9000}}

    with pytest.raises(PayloadTooLarge):
        await bus.publish("sse:test:ch", big_message)

    # pg_notify must NOT be called
    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_pg_bus_publish_exactly_at_limit_passes() -> None:
    """Payload exactly at 8000 bytes must NOT raise."""
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    # Build a payload that is exactly 8000 bytes when JSON-encoded
    # Base: {"type":"x","channel":"c","payload":"..."}
    # We'll fill up to the limit
    base = json.dumps({"type": "x", "channel": "c", "payload": ""})
    fill_len = 8000 - len(base.encode()) - 2  # -2 for the quotes around empty string
    big_val = "A" * max(0, fill_len)
    msg = {"type": "x", "payload": big_val}
    raw = json.dumps({**msg, "channel": "c"})
    assert len(raw.encode()) <= 8000

    # Should not raise
    await bus.publish("c", msg)


# ---------------------------------------------------------------------------
# PgNotificationBus — subscribe() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pg_bus_subscribe_yields_incoming_messages() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    received: list[dict[str, Any]] = []

    async def _consume() -> None:
        async for msg in bus.subscribe("sse:thread:1", max_messages=1):
            received.append(msg)

    # Start consuming, then inject a notification
    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)  # yield so subscribe() registers listener
    msg_data = {"type": "done", "payload": {"message_id": "uuid-1"}, "channel": "sse:thread:1"}
    fake.inject_notify("sse:thread:1", json.dumps(msg_data))
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0]["type"] == "done"


@pytest.mark.asyncio
async def test_pg_bus_subscribe_issues_listen_and_unlisten() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    async def _consume() -> None:
        async for _ in bus.subscribe("sse:job:42", max_messages=1):
            pass

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:42", json.dumps({"type": "done", "channel": "sse:job:42"}))
    await asyncio.wait_for(task, timeout=2.0)

    sql_statements = [e[0] for e in fake.executed]
    assert any("LISTEN" in s for s in sql_statements)
    assert any("UNLISTEN" in s for s in sql_statements)


@pytest.mark.asyncio
async def test_pg_bus_subscribe_releases_connection_on_close() -> None:
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    async def _consume() -> None:
        async for _ in bus.subscribe("sse:job:99", max_messages=1):
            pass

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:99", json.dumps({"type": "done", "channel": "sse:job:99"}))
    await asyncio.wait_for(task, timeout=2.0)

    bus._release_dedicated.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pg_bus_subscribe_ignores_invalid_json() -> None:
    """Malformed payloads are logged and skipped; iterator continues."""
    fake = FakeAsyncpgConnection()
    bus = _make_bus_with_fake_conn(fake)

    received: list[dict[str, Any]] = []

    async def _consume() -> None:
        async for msg in bus.subscribe("sse:job:bad", max_messages=1):
            received.append(msg)

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    # First: invalid JSON (should be skipped)
    fake.inject_notify("sse:job:bad", "not-json")
    await asyncio.sleep(0)
    # Second: valid JSON (should be yielded)
    fake.inject_notify("sse:job:bad", json.dumps({"type": "ok", "channel": "sse:job:bad"}))
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0]["type"] == "ok"


# ---------------------------------------------------------------------------
# JobProgressService (in-memory) tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_progress_service_stores_job_state() -> None:
    svc = JobProgressService()
    await svc.set_state("job-001", JobState.RUNNING, progress=25)
    data = await svc.get_state("job-001")
    assert data is not None
    assert data["state"] == "running"
    assert data["progress"] == 25


@pytest.mark.asyncio
async def test_job_progress_service_get_state_returns_none_when_missing() -> None:
    svc = JobProgressService()
    result = await svc.get_state("nonexistent-job")
    assert result is None


@pytest.mark.asyncio
async def test_job_progress_service_complete_sets_done_state() -> None:
    svc = JobProgressService()
    await svc.complete("job-002", message_id="msg-uuid-42")
    data = await svc.get_state("job-002")
    assert data is not None
    assert data["state"] == "done"
    assert data["message_id"] == "msg-uuid-42"


@pytest.mark.asyncio
async def test_job_progress_service_fail_sets_error_state() -> None:
    svc = JobProgressService()
    await svc.fail("job-003", error="timeout exceeded")
    data = await svc.get_state("job-003")
    assert data is not None
    assert data["state"] == "error"
    assert data["error"] == "timeout exceeded"


@pytest.mark.asyncio
async def test_job_progress_service_ttl_eviction() -> None:
    """Expired entries are evicted on read."""
    import time

    svc = JobProgressService()
    await svc.set_state("job-ttl", JobState.RUNNING)
    # Manually expire the entry
    svc._store["job-ttl"].expires_at = time.monotonic() - 1

    result = await svc.get_state("job-ttl")
    assert result is None
    assert "job-ttl" not in svc._store
