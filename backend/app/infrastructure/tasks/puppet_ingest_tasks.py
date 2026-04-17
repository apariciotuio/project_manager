"""EP-13 — Celery tasks for Puppet ingest pipeline.

process_puppet_ingest:
  1. Scan puppet_sync_outbox for pending 'index' rows (work_item upserts).
  2. For each, create a puppet_ingest_request row.
  3. Call PuppetIngestService.dispatch_pending() to call Puppet and record results.
  4. Mark outbox rows success/failed accordingly.

Follows the same pattern as drain_puppet_outbox (lru_cache trap avoidance,
_build_deps monkeypatchable, asyncio.run() wrapper).

Retry: exponential backoff via Celery task-level retries (max_retries=3).
Timeout: 30s (soft_time_limit).
acks_late=True: safe re-execution if worker crashes mid-batch.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.config.celery_app import celery_app

logger = logging.getLogger(__name__)

_TASK_NAME = "process_puppet_ingest"


async def _build_ingest_deps() -> dict[str, Any]:
    """Build DB session + PuppetClient + repos from live settings.

    Deferred imports to avoid lru_cache trap (see project_settings_lru_cache_trap.md).
    """
    from app.config.settings import get_settings
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.puppet_ingest_request_repository_impl import (
        PuppetIngestRequestRepositoryImpl,
    )
    from app.infrastructure.persistence.puppet_outbox_repository_impl import (
        PuppetOutboxRepositoryImpl,
    )

    settings = get_settings()

    if settings.puppet.use_fake:
        from tests.fakes.fake_puppet_client import FakePuppetClient

        puppet_client: Any = FakePuppetClient()
    else:
        from app.infrastructure.adapters.puppet_http_client import PuppetHTTPClient

        puppet_client = PuppetHTTPClient(
            base_url=settings.puppet.base_url,
            api_key=settings.puppet.api_key,
        )

    factory = get_session_factory()
    session = factory()
    await session.__aenter__()

    return {
        "puppet_client": puppet_client,
        "outbox_repo": PuppetOutboxRepositoryImpl(session),
        "ingest_repo": PuppetIngestRequestRepositoryImpl(session),
        "_session": session,
    }


@celery_app.task(  # type: ignore[untyped-decorator]
    name=_TASK_NAME,
    queue="puppet_sync",
    bind=True,
    max_retries=3,
    acks_late=True,
    soft_time_limit=30,
)
def process_puppet_ingest(self: Any, *, batch_limit: int = 50) -> dict[str, int]:
    """Drain outbox → create ingest_request rows → dispatch to Puppet.

    Returns {"outbox_processed": N, "ingest_dispatched": M}.
    Retries with exponential backoff on unexpected errors.
    """

    async def _run() -> dict[str, int]:
        deps = await _build_ingest_deps()
        outbox_repo = deps["outbox_repo"]
        ingest_repo = deps["ingest_repo"]
        puppet_client = deps["puppet_client"]
        session = deps.get("_session")

        from app.application.services.puppet_ingest_service import PuppetIngestService

        ingest_svc = PuppetIngestService(
            ingest_repo=ingest_repo,
            puppet_client=puppet_client,
        )

        outbox_processed = 0
        ingest_dispatched = 0

        try:
            # Step 1: claim outbox rows (operation='index' = work_item upserted)
            rows = await outbox_repo.claim_batch(limit=batch_limit)

            for row in rows:
                row_id: UUID = row["id"]
                operation: str = row["operation"]
                work_item_id: UUID = row["work_item_id"]
                workspace_id: UUID = row["workspace_id"]
                payload: dict[str, Any] = row["payload"]

                if operation == "index":
                    # Step 2: create ingest_request row
                    await ingest_svc.enqueue(
                        workspace_id=workspace_id,
                        work_item_id=work_item_id,
                        source_kind="outbox",
                        payload=payload,
                    )
                    await outbox_repo.mark_success(row_id)
                    logger.info(
                        "puppet_ingest.outbox_enqueued work_item=%s row=%s",
                        work_item_id,
                        row_id,
                    )
                elif operation == "delete":
                    # Direct delete path — no ingest_request needed for deletions
                    try:
                        await puppet_client.delete_document(str(work_item_id))
                        await outbox_repo.mark_success(row_id)
                        logger.info("puppet_ingest.delete_ok work_item=%s", work_item_id)
                    except Exception as exc:  # noqa: BLE001
                        await outbox_repo.mark_failed(row_id, str(exc)[:500])
                        logger.error(
                            "puppet_ingest.delete_failed work_item=%s err=%s", work_item_id, exc
                        )
                else:
                    logger.warning(
                        "puppet_ingest.unknown_op op=%s row=%s", operation, row_id
                    )
                    await outbox_repo.mark_failed(row_id, f"unknown operation: {operation}")

                outbox_processed += 1

            # Step 3: dispatch queued ingest_request rows for all workspaces
            # that had items in this batch
            dispatched_workspace_ids: set[UUID] = {
                row["workspace_id"]
                for row in rows
                if row["operation"] == "index"
            }
            for ws_id in dispatched_workspace_ids:
                n = await ingest_svc.dispatch_pending(ws_id, limit=batch_limit)
                ingest_dispatched += n

            if session is not None:
                await session.commit()

        except Exception as exc:
            logger.exception("puppet_ingest.task_error: %s", exc)
            if session is not None:
                await session.rollback()
            raise
        finally:
            if session is not None:
                await session.__aexit__(None, None, None)

        return {"outbox_processed": outbox_processed, "ingest_dispatched": ingest_dispatched}

    try:
        result: dict[str, int] = asyncio.run(_run())
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("puppet_ingest.retry: %s", exc)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries) from exc
