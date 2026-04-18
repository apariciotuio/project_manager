"""Tests for SSE infrastructure — RED phase.

Tests:
  - RedisPubSub: publish and subscribe message delivery via fake Redis
  - SseHandler: StreamingResponse with correct SSE frame format
  - JobProgressService: write/read job state in Redis
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.sse.redis_pubsub import RedisPubSub
from app.infrastructure.sse.job_progress_service import JobProgressService, JobState


# ---------------------------------------------------------------------------
# Fake Redis for pub/sub
# ---------------------------------------------------------------------------


class FakePubSubMessage:
    def __init__(self, data: str) -> None:
        self.type = "message"
        self.data = data


class FakeSubscription:
    """Simulates redis.asyncio PubSub object."""

    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages
        self._idx = 0

    async def subscribe(self, channel: str) -> None:
        pass

    async def unsubscribe(self, channel: str) -> None:
        pass

    async def get_message(
        self, ignore_subscribe_messages: bool = True, timeout: float = 0.1
    ) -> dict[str, Any] | None:
        if self._idx < len(self._messages):
            msg = self._messages[self._idx]
            self._idx += 1
            return msg
        return None

    async def aclose(self) -> None:
        pass


class FakeRedisForPubSub:
    """Minimal fake Redis for pub/sub + get/set/setex/delete."""

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._published: list[tuple[str, str]] = []
        self._pubsub_messages: list[dict[str, Any]] = []

    def pubsub(self) -> FakeSubscription:
        return FakeSubscription(self._pubsub_messages)

    async def publish(self, channel: str, message: str) -> None:
        self._published.append((channel, message))

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def inject_message(self, channel: str, data: str) -> None:
        self._pubsub_messages.append({"type": "message", "data": data})


# ---------------------------------------------------------------------------
# RedisPubSub tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pubsub_publish_sends_json_to_channel() -> None:
    fake = FakeRedisForPubSub()
    pubsub = RedisPubSub(fake)  # type: ignore[arg-type]

    await pubsub.publish("sse:thread:abc", {"type": "token", "payload": {"text": "hello"}})

    assert len(fake._published) == 1
    channel, raw = fake._published[0]
    assert channel == "sse:thread:abc"
    decoded = json.loads(raw)
    assert decoded["type"] == "token"
    assert decoded["payload"]["text"] == "hello"


@pytest.mark.asyncio
async def test_pubsub_publish_includes_channel_in_message() -> None:
    """Published message includes the channel field per SSE frame spec."""
    fake = FakeRedisForPubSub()
    pubsub = RedisPubSub(fake)  # type: ignore[arg-type]

    await pubsub.publish("sse:user:xyz", {"type": "notify", "payload": {}})

    _, raw = fake._published[0]
    decoded = json.loads(raw)
    assert decoded["channel"] == "sse:user:xyz"


@pytest.mark.asyncio
async def test_pubsub_subscribe_yields_messages() -> None:
    fake = FakeRedisForPubSub()
    msg = json.dumps({"type": "done", "payload": {"message_id": "uuid-1"}, "channel": "sse:thread:1"})
    fake.inject_message("sse:thread:1", msg)

    pubsub = RedisPubSub(fake)  # type: ignore[arg-type]

    received: list[dict[str, Any]] = []
    async for event in pubsub.subscribe("sse:thread:1", max_messages=1):
        received.append(event)

    assert len(received) == 1
    assert received[0]["type"] == "done"


# ---------------------------------------------------------------------------
# JobProgressService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_progress_service_stores_job_state() -> None:
    fake = FakeRedisForPubSub()
    svc = JobProgressService(fake)  # type: ignore[arg-type]

    await svc.set_state("job-001", JobState.RUNNING, progress=25)

    raw = await fake.get("job:job-001")
    assert raw is not None
    data = json.loads(raw)
    assert data["state"] == "running"
    assert data["progress"] == 25


@pytest.mark.asyncio
async def test_job_progress_service_get_state_returns_none_when_missing() -> None:
    fake = FakeRedisForPubSub()
    svc = JobProgressService(fake)  # type: ignore[arg-type]

    result = await svc.get_state("nonexistent-job")
    assert result is None


@pytest.mark.asyncio
async def test_job_progress_service_complete_sets_done_state() -> None:
    fake = FakeRedisForPubSub()
    svc = JobProgressService(fake)  # type: ignore[arg-type]

    await svc.complete("job-002", message_id="msg-uuid-42")

    raw = await fake.get("job:job-002")
    assert raw is not None
    data = json.loads(raw)
    assert data["state"] == "done"
    assert data["message_id"] == "msg-uuid-42"


@pytest.mark.asyncio
async def test_job_progress_service_fail_sets_error_state() -> None:
    fake = FakeRedisForPubSub()
    svc = JobProgressService(fake)  # type: ignore[arg-type]

    await svc.fail("job-003", error="timeout exceeded")

    raw = await fake.get("job:job-003")
    assert raw is not None
    data = json.loads(raw)
    assert data["state"] == "error"
    assert data["error"] == "timeout exceeded"
