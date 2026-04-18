"""Tests for ProgressTaskMixin when job_service is None.

The main test_progress_task.py covers the case where a JobProgressService is
injected.  These tests cover the branch where job_service=None — i.e. the
mixin is used as a pure publisher without persistent state (the docstring
says "When omitted, publish_done / publish_error skip state writes").

Cases:
  - publish_done with no job_service still publishes SSE frame
  - publish_done with no job_service does NOT call any state write
  - publish_error with no job_service still publishes SSE frame
  - publish_error with no job_service does NOT call any state write
  - publish_progress with no job_service publishes progress frame (baseline)
  - publish_done payload contains message_id in done frame
  - publish_error payload contains message key in error frame
"""
from __future__ import annotations

from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fake publisher
# ---------------------------------------------------------------------------


class FakePublisher:
    def __init__(self) -> None:
        self._published: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        self._published.append((channel, message))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_publish_done_without_job_service_emits_done_frame() -> None:
    """publish_done with job_service=None still emits the SSE done frame."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_done("job-no-svc-1", message_id="msg-xyz")

    assert len(pub._published) == 1
    channel, msg = pub._published[0]
    assert channel == "sse:job:job-no-svc-1"
    assert msg["type"] == "done"


@pytest.mark.asyncio
async def test_publish_done_without_job_service_payload_contains_message_id() -> None:
    """done frame payload carries message_id even without persistent service."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_done("job-payload-check", message_id="msg-abc-42")

    _, msg = pub._published[0]
    assert msg["payload"]["message_id"] == "msg-abc-42"


@pytest.mark.asyncio
async def test_publish_done_without_job_service_makes_no_state_writes() -> None:
    """When job_service is None, publish_done does not attempt to write state.

    We verify indirectly: no exception raised and only one publish call made.
    """
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub, job_service=None)  # explicit None

    await mixin.publish_done("job-stateless-done", message_id="m1")

    # Exactly one call — the SSE publish. No extra calls from a state write.
    assert len(pub._published) == 1


@pytest.mark.asyncio
async def test_publish_error_without_job_service_emits_error_frame() -> None:
    """publish_error with job_service=None still emits the SSE error frame."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_error("job-no-svc-2", error_msg="network timeout")

    assert len(pub._published) == 1
    channel, msg = pub._published[0]
    assert channel == "sse:job:job-no-svc-2"
    assert msg["type"] == "error"


@pytest.mark.asyncio
async def test_publish_error_without_job_service_payload_contains_message() -> None:
    """error frame payload carries 'message' key."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub)  # type: ignore[arg-type]

    await mixin.publish_error("job-err-payload", error_msg="upstream failed")

    _, msg = pub._published[0]
    assert msg["payload"]["message"] == "upstream failed"


@pytest.mark.asyncio
async def test_publish_error_without_job_service_makes_no_state_writes() -> None:
    """When job_service is None, publish_error does not attempt to write state."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub, job_service=None)

    await mixin.publish_error("job-stateless-err", error_msg="boom")

    assert len(pub._published) == 1


@pytest.mark.asyncio
async def test_publish_progress_without_job_service_emits_frame() -> None:
    """publish_progress never writes state regardless; verify it still publishes."""
    from app.infrastructure.tasks.progress_task import ProgressTaskMixin

    pub = FakePublisher()
    mixin = ProgressTaskMixin(publisher=pub, job_service=None)

    await mixin.publish_progress("job-p-no-svc", pct=77)

    assert len(pub._published) == 1
    _, msg = pub._published[0]
    assert msg["type"] == "progress"
    assert msg["payload"]["pct"] == 77
