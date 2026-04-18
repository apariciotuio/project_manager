"""Tests for ProgressTaskMixin.

ProgressTask:
  - publish_progress(job_id, pct) publishes progress frame to sse:job:{job_id}
  - publish_done(job_id, message_id) publishes done frame + updates job state
  - publish_error(job_id, error_msg) publishes error frame + updates job state
  - All helpers are async-safe (called inside asyncio.run block in task body)
  - publish_progress does NOT update persistent job state (hot path, pub only)
  - publish_done/publish_error update JobProgressService state
"""
from __future__ import annotations

from typing import Any

import pytest

from app.infrastructure.sse.job_progress_service import JobProgressService, JobState


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakePublisher:
    """Satisfies _PublishProto — records all publish calls as (channel, message) tuples."""

    def __init__(self) -> None:
        self._published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        self._published.append((channel, message))


# ---------------------------------------------------------------------------
# ProgressTask helpers tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_progress_task_publish_progress_sends_frame() -> None:
    """publish_progress publishes a progress SSE frame to sse:job:{job_id}."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_progress("job-001", pct=42)

    assert len(pub._published) == 1
    channel, msg = pub._published[0]
    assert channel == "sse:job:job-001"
    assert msg["type"] == "progress"
    assert msg["payload"]["pct"] == 42


@pytest.mark.asyncio
async def test_progress_task_publish_done_sends_done_frame_and_updates_state() -> None:
    """publish_done publishes done frame and writes JobState.DONE to job service."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    job_svc = JobProgressService()
    mixin = ProgressTaskMixin(publisher=pub, job_service=job_svc)  # type: ignore[arg-type]

    await mixin.publish_done("job-002", message_id="msg-abc")

    # SSE frame published
    assert len(pub._published) == 1
    channel, msg = pub._published[0]
    assert channel == "sse:job:job-002"
    assert msg["type"] == "done"
    assert msg["payload"]["message_id"] == "msg-abc"

    # Job state updated via JobProgressService
    state = await job_svc.get_state("job-002")
    assert state is not None
    assert state["state"] == "done"
    assert state["message_id"] == "msg-abc"


@pytest.mark.asyncio
async def test_progress_task_publish_error_sends_error_frame_and_updates_state() -> None:
    """publish_error publishes error frame and writes JobState.ERROR to job service."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    job_svc = JobProgressService()
    mixin = ProgressTaskMixin(publisher=pub, job_service=job_svc)  # type: ignore[arg-type]

    await mixin.publish_error("job-003", error_msg="downstream timeout")

    # SSE frame published
    assert len(pub._published) == 1
    channel, msg = pub._published[0]
    assert channel == "sse:job:job-003"
    assert msg["type"] == "error"
    assert msg["payload"]["message"] == "downstream timeout"

    # Job state updated via JobProgressService
    state = await job_svc.get_state("job-003")
    assert state is not None
    assert state["state"] == "error"
    assert state["error"] == "downstream timeout"


@pytest.mark.asyncio
async def test_progress_task_publish_progress_does_not_write_job_state() -> None:
    """publish_progress is a hot path — no state write for persistent state."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    job_svc = JobProgressService()
    mixin = ProgressTaskMixin(publisher=pub, job_service=job_svc)  # type: ignore[arg-type]

    await mixin.publish_progress("job-004", pct=10)
    await mixin.publish_progress("job-004", pct=20)
    await mixin.publish_progress("job-004", pct=30)

    # Only publish calls — no persistent state written
    assert all(ch == "sse:job:job-004" for ch, _ in pub._published)
    assert await job_svc.get_state("job-004") is None


@pytest.mark.asyncio
async def test_progress_task_channel_uses_sse_job_prefix() -> None:
    """Channel is always sse:job:{job_id} regardless of job_id format."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_progress("550e8400-e29b-41d4-a716-446655440000", pct=5)

    channel, _ = pub._published[0]
    assert channel == "sse:job:550e8400-e29b-41d4-a716-446655440000"
