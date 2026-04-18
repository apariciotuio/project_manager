"""Unit tests for PgNotificationBus.

Mirrors test_sse_infrastructure.py PgNotificationBus section but lives in
the canonical location (tests/unit/infrastructure/sse/) as required by PR3 spec.

Tests use a FakeAsyncpgConnection — no real DB needed.

Coverage:
  - publish() serializes to JSON and calls pg_notify
  - publish() includes channel field in payload
  - publish() raises PayloadTooLarge for payloads > 8000 bytes
  - subscribe() yields messages via listener callback
  - subscribe() issues LISTEN then UNLISTEN
  - subscribe() releases dedicated connection in finally
  - subscribe() skips malformed JSON payloads
"""
from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.infrastructure.sse.pg_notification_bus import PgNotificationBus, PayloadTooLarge


# ---------------------------------------------------------------------------
# Fake asyncpg connection
# ---------------------------------------------------------------------------


class FakeAsyncpgConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, ...]] = []
        self._listeners: dict[str, Any] = {}

    async def execute(self, sql: str, *args: Any) -> None:
        self.executed.append((sql, *args))

    async def add_listener(self, channel: str, callback: Any) -> None:
        self._listeners[channel] = callback

    async def remove_listener(self, channel: str, callback: Any) -> None:
        self._listeners.pop(channel, None)

    async def close(self) -> None:
        pass

    def inject_notify(self, channel: str, payload: str) -> None:
        cb = self._listeners.get(channel)
        if cb is not None:
            cb(self, 0, channel, payload)


def _bus(fake: FakeAsyncpgConnection) -> PgNotificationBus:
    bus = PgNotificationBus(dsn="postgresql://fake/fake")
    bus._acquire_pooled = AsyncMock(return_value=fake)  # type: ignore[method-assign]
    bus._release_pooled = AsyncMock()  # type: ignore[method-assign]
    bus._acquire_dedicated = AsyncMock(return_value=fake)  # type: ignore[method-assign]
    bus._release_dedicated = AsyncMock()  # type: ignore[method-assign]
    return bus


# ---------------------------------------------------------------------------
# publish() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_calls_pg_notify_with_json_payload() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    await bus.publish("sse:thread:abc", {"type": "token", "payload": {"text": "hello"}})

    assert len(fake.executed) == 1
    sql, channel_arg, payload_arg = fake.executed[0]
    assert "pg_notify" in sql
    assert channel_arg == "sse:thread:abc"
    decoded = json.loads(payload_arg)
    assert decoded["type"] == "token"
    assert decoded["payload"]["text"] == "hello"


@pytest.mark.asyncio
async def test_publish_includes_channel_in_payload() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    await bus.publish("sse:user:xyz", {"type": "notify", "payload": {}})

    _, _, payload_arg = fake.executed[0]
    assert json.loads(payload_arg)["channel"] == "sse:user:xyz"


@pytest.mark.asyncio
async def test_publish_raises_payload_too_large() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(PayloadTooLarge):
        await bus.publish("ch", {"type": "data", "payload": {"x": "A" * 9000}})

    assert len(fake.executed) == 0, "pg_notify must not be called for oversized payload"


@pytest.mark.asyncio
async def test_publish_exactly_at_limit_does_not_raise() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    base = json.dumps({"type": "x", "channel": "c", "payload": ""})
    fill = max(0, 8000 - len(base.encode()) - 2)
    msg = {"type": "x", "payload": "A" * fill}
    assert len(json.dumps({**msg, "channel": "c"}).encode()) <= 8000

    await bus.publish("c", msg)  # must not raise


# ---------------------------------------------------------------------------
# subscribe() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_yields_incoming_messages() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    received: list[dict[str, Any]] = []

    async def _consume() -> None:
        async for msg in bus.subscribe("sse:thread:1", max_messages=1):
            received.append(msg)

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    fake.inject_notify(
        "sse:thread:1",
        json.dumps({"type": "done", "payload": {"message_id": "u1"}, "channel": "sse:thread:1"}),
    )
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0]["type"] == "done"


@pytest.mark.asyncio
async def test_subscribe_issues_listen() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    task = asyncio.create_task(
        _collect(bus, "sse:job:1", max_messages=1, fake=fake)
    )
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:1", json.dumps({"type": "ok", "channel": "sse:job:1"}))
    await asyncio.wait_for(task, timeout=2.0)

    sql_statements = [e[0] for e in fake.executed]
    assert any("LISTEN" in s for s in sql_statements)


@pytest.mark.asyncio
async def test_subscribe_unlisten_on_exhaustion() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    task = asyncio.create_task(_collect(bus, "sse:job:2", max_messages=1, fake=fake))
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:2", json.dumps({"type": "done", "channel": "sse:job:2"}))
    await asyncio.wait_for(task, timeout=2.0)

    sql_statements = [e[0] for e in fake.executed]
    assert any("UNLISTEN" in s for s in sql_statements)


@pytest.mark.asyncio
async def test_subscribe_releases_connection_in_finally() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    task = asyncio.create_task(_collect(bus, "sse:job:3", max_messages=1, fake=fake))
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:3", json.dumps({"type": "done", "channel": "sse:job:3"}))
    await asyncio.wait_for(task, timeout=2.0)

    bus._release_dedicated.assert_called_once()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_subscribe_skips_invalid_json_and_continues() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    received: list[dict[str, Any]] = []

    async def _consume() -> None:
        async for msg in bus.subscribe("sse:job:bad", max_messages=1):
            received.append(msg)

    task = asyncio.create_task(_consume())
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:bad", "not-json")
    await asyncio.sleep(0)
    fake.inject_notify("sse:job:bad", json.dumps({"type": "ok", "channel": "sse:job:bad"}))
    await asyncio.wait_for(task, timeout=2.0)

    assert received == [{"type": "ok", "channel": "sse:job:bad"}]


# ---------------------------------------------------------------------------
# Channel name validation tests (MF-1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_rejects_sql_injection_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        await bus.publish('evil"; DROP TABLE users;--', {"type": "x"})

    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_publish_rejects_channel_with_space() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        await bus.publish("x y", {"type": "x"})

    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_publish_rejects_empty_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        await bus.publish("", {"type": "x"})

    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_publish_rejects_channel_over_63_chars() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        await bus.publish("a" * 64, {"type": "x"})

    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_publish_accepts_valid_job_progress_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    # job_progress:<uuid> format — must pass validation
    await bus.publish("job_progress:550e8400-e29b-41d4-a716-446655440000", {"type": "x"})

    assert len(fake.executed) == 1


@pytest.mark.asyncio
async def test_subscribe_rejects_sql_injection_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        async for _ in bus.subscribe('x"; DROP TABLE users;--'):
            pass

    assert len(fake.executed) == 0


@pytest.mark.asyncio
async def test_subscribe_rejects_channel_with_space() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        async for _ in bus.subscribe("x y"):
            pass


@pytest.mark.asyncio
async def test_subscribe_rejects_empty_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        async for _ in bus.subscribe(""):
            pass


@pytest.mark.asyncio
async def test_subscribe_rejects_channel_over_63_chars() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    with pytest.raises(ValueError, match="invalid channel name"):
        async for _ in bus.subscribe("a" * 64):
            pass


@pytest.mark.asyncio
async def test_subscribe_accepts_valid_sse_thread_channel() -> None:
    fake = FakeAsyncpgConnection()
    bus = _bus(fake)

    task = asyncio.create_task(
        _collect(bus, "sse:thread:550e8400-e29b-41d4-a716-446655440000", max_messages=1, fake=fake)
    )
    await asyncio.sleep(0)
    fake.inject_notify(
        "sse:thread:550e8400-e29b-41d4-a716-446655440000",
        '{"type": "ok", "channel": "sse:thread:550e8400-e29b-41d4-a716-446655440000"}',
    )
    await asyncio.wait_for(task, timeout=2.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _collect(
    bus: PgNotificationBus,
    channel: str,
    *,
    max_messages: int,
    fake: FakeAsyncpgConnection,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    async for msg in bus.subscribe(channel, max_messages=max_messages):
        results.append(msg)
    return results
