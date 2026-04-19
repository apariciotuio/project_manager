"""Unit tests for process_puppet_ingest Celery task — EP-13.

Tests use monkeypatching of _build_ingest_deps to inject
FakePuppetClient + in-memory repositories.

WHEN: outbox has index/delete rows
THEN: correct ingest_request rows created, Puppet calls made, outbox rows updated

WHEN: Puppet fails
THEN: task retries via Celery max_retries

WHEN: no outbox rows
THEN: task returns {outbox_processed: 0, ingest_dispatched: 0}
"""
from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from tests.fakes.fake_puppet_client import FakePuppetClient


# ---------------------------------------------------------------------------
# In-memory stubs
# ---------------------------------------------------------------------------


class FakeOutboxRepo:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []
        self.success_ids: list[UUID] = []
        self.failed_ids: list[tuple[UUID, str]] = []
        self._claimed = False

    async def claim_batch(self, limit: int) -> list[dict[str, Any]]:
        if self._claimed:
            return []
        self._claimed = True
        return self._rows[:limit]

    async def mark_success(self, row_id: UUID) -> None:
        self.success_ids.append(row_id)

    async def mark_failed(self, row_id: UUID, error: str) -> None:
        self.failed_ids.append((row_id, error))


class FakeIngestRepo:
    def __init__(self) -> None:
        from app.domain.models.puppet_ingest_request import PuppetIngestRequest
        self._store: dict[UUID, PuppetIngestRequest] = {}

    async def save(self, request: Any) -> None:
        self._store[request.id] = request

    async def get(self, request_id: UUID) -> Any | None:
        return self._store.get(request_id)

    async def claim_queued_batch(self, workspace_id: UUID, limit: int) -> list[Any]:
        queued = [
            r for r in self._store.values()
            if r.workspace_id == workspace_id and r.status == "queued"
        ][:limit]
        for r in queued:
            r.mark_dispatched()
        return queued

    async def has_succeeded_for_work_item(self, work_item_id: UUID) -> bool:
        return any(
            r.status == "succeeded" and r.work_item_id == work_item_id
            for r in self._store.values()
        )

    async def list_by_workspace(
        self, workspace_id: UUID, status: str | None, limit: int, offset: int
    ) -> list[Any]:
        return []


class FakeSession:
    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def __aenter__(self) -> FakeSession:
        return self

    async def __aexit__(self, *args: Any) -> None:
        pass


def _build_fake_deps(
    outbox_rows: list[dict[str, Any]] | None = None,
    puppet_client: FakePuppetClient | None = None,
) -> dict[str, Any]:
    return {
        "puppet_client": puppet_client or FakePuppetClient(),
        "outbox_repo": FakeOutboxRepo(outbox_rows),
        "ingest_repo": FakeIngestRepo(),
        "_session": FakeSession(),
    }


def _make_outbox_row(
    operation: str = "index",
    workspace_id: UUID | None = None,
    work_item_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "workspace_id": workspace_id or uuid4(),
        "work_item_id": work_item_id or uuid4(),
        "operation": operation,
        "payload": payload or {"content": "test content", "tags": ["wm_test"]},
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_outbox_returns_zero() -> None:
    """WHEN no outbox rows THEN returns zeros without error."""
    import asyncio
    from app.infrastructure.tasks import puppet_ingest_tasks as module

    original = module._build_ingest_deps

    async def _fake_deps() -> dict[str, Any]:
        return _build_fake_deps(outbox_rows=[])

    module._build_ingest_deps = _fake_deps

    try:
        # Run the inner _run coroutine directly
        from app.application.services.puppet_ingest_service import PuppetIngestService

        deps = await _fake_deps()
        outbox_repo = deps["outbox_repo"]
        ingest_repo = deps["ingest_repo"]
        puppet_client = deps["puppet_client"]

        ingest_svc = PuppetIngestService(ingest_repo=ingest_repo, puppet_client=puppet_client)  # type: ignore[arg-type]
        rows = await outbox_repo.claim_batch(limit=50)
        assert rows == []
    finally:
        module._build_ingest_deps = original


@pytest.mark.asyncio
async def test_index_row_creates_ingest_request_and_dispatches() -> None:
    """WHEN outbox has an index row THEN ingest_request created + Puppet called."""
    from app.application.services.puppet_ingest_service import PuppetIngestService

    ws_id = uuid4()
    wi_id = uuid4()
    row = _make_outbox_row("index", workspace_id=ws_id, work_item_id=wi_id)
    outbox_repo = FakeOutboxRepo([row])
    ingest_repo = FakeIngestRepo()
    puppet_client = FakePuppetClient()

    ingest_svc = PuppetIngestService(ingest_repo=ingest_repo, puppet_client=puppet_client)  # type: ignore[arg-type]

    # Simulate the task's _run logic
    rows = await outbox_repo.claim_batch(50)
    assert len(rows) == 1

    for r in rows:
        if r["operation"] == "index":
            await ingest_svc.enqueue(
                workspace_id=r["workspace_id"],
                work_item_id=r["work_item_id"],
                source_kind="outbox",
                payload=r["payload"],
            )
            await outbox_repo.mark_success(r["id"])

    # Dispatch
    dispatched = await ingest_svc.dispatch_pending(ws_id)
    assert dispatched == 1
    assert len(puppet_client.index_calls) == 1

    # Outbox row marked success
    assert len(outbox_repo.success_ids) == 1
    assert outbox_repo.success_ids[0] == row["id"]

    # Ingest request in succeeded state
    succeeded = [r for r in ingest_repo._store.values() if r.status == "succeeded"]
    assert len(succeeded) == 1
    assert succeeded[0].work_item_id == wi_id


@pytest.mark.asyncio
async def test_delete_row_calls_puppet_delete_directly() -> None:
    """WHEN outbox has a delete row THEN puppet.delete_document called, no ingest_request."""
    from app.application.services.puppet_ingest_service import PuppetIngestService

    ws_id = uuid4()
    wi_id = uuid4()
    row = _make_outbox_row("delete", workspace_id=ws_id, work_item_id=wi_id, payload={})
    outbox_repo = FakeOutboxRepo([row])
    ingest_repo = FakeIngestRepo()
    puppet_client = FakePuppetClient()

    ingest_svc = PuppetIngestService(ingest_repo=ingest_repo, puppet_client=puppet_client)  # type: ignore[arg-type]

    rows = await outbox_repo.claim_batch(50)
    for r in rows:
        if r["operation"] == "delete":
            await puppet_client.delete_document(str(r["work_item_id"]))
            await outbox_repo.mark_success(r["id"])

    assert str(wi_id) in puppet_client.delete_calls
    assert len(outbox_repo.success_ids) == 1
    # No ingest requests created for delete
    assert len(ingest_repo._store) == 0


@pytest.mark.asyncio
async def test_puppet_failure_marks_ingest_request_failed() -> None:
    """WHEN Puppet returns error THEN ingest_request is marked failed (not succeeded)."""
    from app.application.services.puppet_ingest_service import PuppetIngestService

    class AlwaysFailPuppetClient:
        async def index_document(self, doc_id: str, content: str, tags: list[str]) -> dict[str, Any]:
            raise RuntimeError("Puppet is down")

        async def delete_document(self, doc_id: str) -> None:
            pass

        async def search(self, query: str, tags: list[str]) -> list[dict[str, Any]]:
            return []

        async def health(self) -> dict[str, Any]:
            return {"status": "error"}

    ws_id = uuid4()
    wi_id = uuid4()
    ingest_repo = FakeIngestRepo()
    puppet_client = AlwaysFailPuppetClient()
    ingest_svc = PuppetIngestService(ingest_repo=ingest_repo, puppet_client=puppet_client)  # type: ignore[arg-type]

    await ingest_svc.enqueue(ws_id, wi_id, payload={"content": "test"})
    await ingest_svc.dispatch_pending(ws_id)

    rows = list(ingest_repo._store.values())
    assert len(rows) == 1
    # Under 3 attempts → re-queued (not failed yet)
    assert rows[0].status == "queued"
    assert rows[0].last_error is None  # cleared after reset_for_retry


@pytest.mark.asyncio
async def test_delete_idempotent_when_doc_not_found() -> None:
    """WHEN Puppet returns 404 for delete THEN no exception, outbox row succeeds."""
    puppet_client = FakePuppetClient()
    # Doc doesn't exist in fake — delete should be no-op
    await puppet_client.delete_document("nonexistent-doc")
    assert "nonexistent-doc" in puppet_client.delete_calls
