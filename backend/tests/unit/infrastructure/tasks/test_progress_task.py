"""RED tests for ProgressTask Celery base class.

ProgressTask:
  - publish_progress(job_id, pct) publishes progress frame to sse:job:{job_id}
  - publish_done(job_id, message_id) publishes done frame + updates job state
  - publish_error(job_id, error_msg) publishes error frame + updates job state
  - All helpers are async-safe (called inside asyncio.run block in task body)
  - publish_progress does NOT update persistent job state (hot path, Redis only)
  - publish_done/publish_error update JobProgressService state
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from app.infrastructure.sse.job_progress_service import JobProgressService, JobState


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._published: list[tuple[str, str]] = []

    def pubsub(self) -> Any:
        raise NotImplementedError("pubsub not needed here")

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


# ---------------------------------------------------------------------------
# ProgressTask helpers tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_task_publish_progress_sends_frame() -> None:
    """publish_progress publishes a progress SSE frame to sse:job:{job_id}."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    fake_redis = FakeRedis()
    mixin = ProgressTaskMixin(redis=fake_redis)  # type: ignore[arg-type]

    await mixin.publish_progress("job-001", pct=42)

    assert len(fake_redis._published) == 1
    channel, raw = fake_redis._published[0]
    assert channel == "sse:job:job-001"
    msg = json.loads(raw)
    assert msg["type"] == "progress"
    assert msg["payload"]["pct"] == 42


@pytest.mark.asyncio
async def test_progress_task_publish_done_sends_done_frame_and_updates_state() -> None:
    """publish_done publishes done frame and writes JobState.DONE to Redis."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    fake_redis = FakeRedis()
    job_svc = JobProgressService(fake_redis)  # type: ignore[arg-type]
    mixin = ProgressTaskMixin(redis=fake_redis, job_service=job_svc)  # type: ignore[arg-type]

    await mixin.publish_done("job-002", message_id="msg-abc")

    # SSE frame published
    assert len(fake_redis._published) == 1
    channel, raw = fake_redis._published[0]
    assert channel == "sse:job:job-002"
    msg = json.loads(raw)
    assert msg["type"] == "done"
    assert msg["payload"]["message_id"] == "msg-abc"

    # Job state updated
    state_raw = await fake_redis.get("job:job-002")
    assert state_raw is not None
    state = json.loads(state_raw)
    assert state["state"] == "done"
    assert state["message_id"] == "msg-abc"


@pytest.mark.asyncio
async def test_progress_task_publish_error_sends_error_frame_and_updates_state() -> None:
    """publish_error publishes error frame and writes JobState.ERROR to Redis."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    fake_redis = FakeRedis()
    job_svc = JobProgressService(fake_redis)  # type: ignore[arg-type]
    mixin = ProgressTaskMixin(redis=fake_redis, job_service=job_svc)  # type: ignore[arg-type]

    await mixin.publish_error("job-003", error_msg="downstream timeout")

    # SSE frame published
    assert len(fake_redis._published) == 1
    channel, raw = fake_redis._published[0]
    assert channel == "sse:job:job-003"
    msg = json.loads(raw)
    assert msg["type"] == "error"
    assert msg["payload"]["message"] == "downstream timeout"

    # Job state updated
    state_raw = await fake_redis.get("job:job-003")
    assert state_raw is not None
    state = json.loads(state_raw)
    assert state["state"] == "error"
    assert state["error"] == "downstream timeout"


@pytest.mark.asyncio
async def test_progress_task_publish_progress_does_not_write_job_state() -> None:
    """publish_progress is a hot path — no Redis SET for persistent state."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    fake_redis = FakeRedis()
    mixin = ProgressTaskMixin(redis=fake_redis)  # type: ignore[arg-type]

    await mixin.publish_progress("job-004", pct=10)
    await mixin.publish_progress("job-004", pct=20)
    await mixin.publish_progress("job-004", pct=30)

    # Only publish calls, no setex
    assert all(ch == "sse:job:job-004" for ch, _ in fake_redis._published)
    assert await fake_redis.get("job:job-004") is None


@pytest.mark.asyncio
async def test_progress_task_channel_uses_sse_job_prefix() -> None:
    """Channel is always sse:job:{job_id} regardless of job_id format."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    fake_redis = FakeRedis()
    mixin = ProgressTaskMixin(redis=fake_redis)  # type: ignore[arg-type]

    await mixin.publish_progress("550e8400-e29b-41d4-a716-446655440000", pct=5)

    channel, _ = fake_redis._published[0]
    assert channel == "sse:job:550e8400-e29b-41d4-a716-446655440000"
