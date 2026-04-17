"""Unit tests for PuppetIngestRequest domain model.

WHEN: state transitions are applied
THEN: status, fields, and invariants behave correctly
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.puppet_ingest_request import PuppetIngestRequest


def _make() -> PuppetIngestRequest:
    return PuppetIngestRequest.create(
        workspace_id=uuid4(),
        source_kind="outbox",
        work_item_id=uuid4(),
        payload={"content": "hello"},
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_create_defaults_to_queued() -> None:
    req = _make()
    assert req.status == "queued"
    assert req.attempts == 0
    assert req.puppet_doc_id is None
    assert req.last_error is None
    assert req.succeeded_at is None


def test_create_invalid_source_kind_raises() -> None:
    with pytest.raises(ValueError, match="source_kind"):
        PuppetIngestRequest.create(workspace_id=uuid4(), source_kind="bad")


def test_create_all_source_kinds() -> None:
    for kind in ("outbox", "manual", "webhook"):
        req = PuppetIngestRequest.create(workspace_id=uuid4(), source_kind=kind)
        assert req.source_kind == kind


# ---------------------------------------------------------------------------
# mark_dispatched
# ---------------------------------------------------------------------------


def test_mark_dispatched_increments_attempts() -> None:
    req = _make()
    req.mark_dispatched()
    assert req.status == "dispatched"
    assert req.attempts == 1


def test_mark_dispatched_twice() -> None:
    req = _make()
    req.mark_dispatched()
    req.mark_failed("err")
    req.mark_dispatched()
    assert req.attempts == 2


# ---------------------------------------------------------------------------
# mark_succeeded
# ---------------------------------------------------------------------------


def test_mark_succeeded_sets_doc_id_and_timestamp() -> None:
    req = _make()
    req.mark_dispatched()
    req.mark_succeeded("puppet-doc-123")
    assert req.status == "succeeded"
    assert req.puppet_doc_id == "puppet-doc-123"
    assert req.succeeded_at is not None
    assert req.last_error is None


# ---------------------------------------------------------------------------
# mark_failed
# ---------------------------------------------------------------------------


def test_mark_failed_records_error() -> None:
    req = _make()
    req.mark_dispatched()
    req.mark_failed("connection timeout")
    assert req.status == "failed"
    assert req.last_error == "connection timeout"
    assert req.puppet_doc_id is None


def test_mark_failed_truncates_long_error() -> None:
    req = _make()
    req.mark_dispatched()
    long_error = "x" * 600
    req.mark_failed(long_error)
    assert len(req.last_error) == 500  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# mark_skipped
# ---------------------------------------------------------------------------


def test_mark_skipped() -> None:
    req = _make()
    req.mark_skipped("already succeeded via previous row")
    assert req.status == "skipped"
    assert "already succeeded" in (req.last_error or "")


# ---------------------------------------------------------------------------
# reset_for_retry
# ---------------------------------------------------------------------------


def test_reset_for_retry_requeues() -> None:
    req = _make()
    req.mark_dispatched()
    req.mark_failed("err")
    req.reset_for_retry()
    assert req.status == "queued"
    assert req.attempts == 0
    assert req.last_error is None


def test_reset_for_retry_clears_last_error() -> None:
    req = _make()
    req.mark_failed("something broke")
    req.reset_for_retry()
    assert req.last_error is None
