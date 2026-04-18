"""EP-13 — Async function for draining the Puppet sync outbox.

Plain async function — no Celery. Triggered via:
  POST /api/v1/internal/jobs/drain_puppet_outbox/run (superadmin)
Host cron hits that endpoint on the desired schedule.

_build_deps is monkeypatch-able for tests.

# TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


async def _build_deps() -> dict[str, Any]:
    """Build DB session + PuppetClient from live settings."""
    from app.config.settings import get_settings
    from app.infrastructure.persistence.database import get_session_factory
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
        "_session": session,
    }


async def drain_puppet_outbox(*, batch_limit: int = 50) -> int:
    """Claim a batch of outbox rows and call PuppetClient for each.

    Returns the number of rows processed (success + failed).

    # TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed.
    """
    deps = await _build_deps()
    puppet_client = deps["puppet_client"]
    outbox_repo = deps["outbox_repo"]
    session = deps.get("_session")
    processed = 0
    try:
        rows = await outbox_repo.claim_batch(limit=batch_limit)
        for row in rows:
            row_id: UUID = row["id"]
            operation: str = row["operation"]
            work_item_id: str = str(row["work_item_id"])
            payload: dict[str, Any] = row["payload"]
            try:
                if operation == "index":
                    content: str = payload.get("content", "")
                    tags: list[str] = payload.get("tags", [])
                    await puppet_client.index_document(work_item_id, content, tags)
                elif operation == "delete":
                    await puppet_client.delete_document(work_item_id)
                else:
                    logger.warning("puppet_sync unknown operation=%s id=%s", operation, row_id)
                    await outbox_repo.mark_failed(row_id, f"unknown operation: {operation}")
                    continue

                await outbox_repo.mark_success(row_id)
                logger.info(
                    "puppet_sync.done id=%s op=%s work_item=%s",
                    row_id,
                    operation,
                    work_item_id,
                )
            except Exception as exc:  # noqa: BLE001
                error_msg = str(exc)[:500]
                await outbox_repo.mark_failed(row_id, error_msg)
                logger.error("puppet_sync.failed id=%s error=%s", row_id, error_msg)

            processed += 1

        if session is not None:
            await session.commit()
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)

    return processed
