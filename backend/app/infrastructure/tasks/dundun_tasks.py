"""EP-03 Phase 6 — Async functions for Dundun agent invocations.

All functions are plain async — no Celery. Callers use FastAPI BackgroundTasks:
  background_tasks.add_task(invoke_suggestion_agent, work_item_id=..., ...)

Pattern:
  - Each function is async; internal DB + HTTP work is awaited directly.
  - Session factory and DundunClient are constructed INSIDE the function body to
    respect the get_settings lru_cache trap: module-level imports capture a stale
    wrapper; deferred imports inside functions always get the live settings.
  - `_build_deps` is a module-level async factory for testability. Tests monkeypatch
    it to inject FakeDundunClient + fake repos without touching the DB.

# TODO(pg-jobs): crash mid-run = silent failure for background invocations;
#   move to pg jobs table if reliability needed.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal async factory — monkeypatched in tests
# ---------------------------------------------------------------------------


async def _build_deps() -> dict[str, Any]:
    """Build DB session + repos + DundunClient from live settings.

    Returns a dict with:
      dundun_client: DundunClient
      suggestion_repo: IAssistantSuggestionRepository
      gap_repo: IGapFindingRepository

    Deferred imports are intentional — see get_settings lru_cache trap.
    """
    from app.config.settings import get_settings
    from app.infrastructure.adapters.dundun_http_client import DundunHTTPClient
    from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
        AssistantSuggestionRepositoryImpl,
    )
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.gap_finding_repository_impl import (
        GapFindingRepositoryImpl,
    )

    settings = get_settings()

    if settings.dundun.use_fake:
        if settings.app.env == "production":
            logger.error(
                "FakeDundunClient requested but APP_ENV=production — refusing to start fake client. "
                "Set DUNDUN_USE_FAKE=false in production."
            )
            raise RuntimeError("FakeDundunClient not allowed in production")
        from app.infrastructure.fakes.fake_dundun_client import FakeDundunClient

        dundun_client: Any = FakeDundunClient()
    else:
        dundun_client = DundunHTTPClient(
            base_url=settings.dundun.base_url,
            service_key=settings.dundun.service_key,
            http_timeout=settings.dundun.http_timeout,
        )

    factory = get_session_factory()

    # We open a session and return repos that hold a reference to it.
    # The caller is responsible for calling session.aclose() when done.
    session = factory()
    await session.__aenter__()

    return {
        "dundun_client": dundun_client,
        "suggestion_repo": AssistantSuggestionRepositoryImpl(session),
        "gap_repo": GapFindingRepositoryImpl(session),
        "_session": session,
    }


# ---------------------------------------------------------------------------
# invoke_suggestion_agent
# ---------------------------------------------------------------------------


async def invoke_suggestion_agent(
    *,
    work_item_id: str,
    user_id: str,
    batch_id: str,
    thread_id: str | None = None,
) -> str:
    """Invoke Dundun's wm_suggestion_agent. Returns the Dundun request_id.

    Idempotent on retry: if any suggestion row for this batch_id already has a
    dundun_request_id, Dundun was already called — return the existing id and
    skip re-invocation.

    # TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed.
    """
    deps = await _build_deps()
    dundun_client = deps["dundun_client"]
    suggestion_repo = deps["suggestion_repo"]
    session = deps.get("_session")
    try:
        from app.config.settings import get_settings
        settings = get_settings()

        # Idempotency check: scan existing batch rows for a prior request_id.
        batch_uuid = UUID(batch_id)
        existing = await suggestion_repo.get_by_batch_id(batch_uuid)
        for row in existing:
            if row.dundun_request_id:
                logger.info(
                    "invoke_suggestion_agent skipped (already invoked) "
                    "batch_id=%s request_id=%s",
                    batch_id,
                    row.dundun_request_id,
                )
                return str(row.dundun_request_id)

        result = await dundun_client.invoke_agent(
            agent="wm_suggestion_agent",
            user_id=UUID(user_id),
            conversation_id=thread_id,
            work_item_id=UUID(work_item_id),
            callback_url=settings.dundun.callback_url,
            payload={"batch_id": batch_id},
        )
        request_id: str = str(result["request_id"])
        logger.info(
            "invoke_suggestion_agent dispatched work_item=%s batch_id=%s request_id=%s",
            work_item_id,
            batch_id,
            request_id,
        )
        return request_id
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# invoke_gap_agent
# ---------------------------------------------------------------------------


async def invoke_gap_agent(
    *,
    work_item_id: str,
    user_id: str,
) -> str:
    """Invoke Dundun's wm_gap_agent. Returns the Dundun request_id.

    # TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed.
    """
    deps = await _build_deps()
    dundun_client = deps["dundun_client"]
    session = deps.get("_session")
    try:
        from app.config.settings import get_settings
        settings = get_settings()

        result = await dundun_client.invoke_agent(
            agent="wm_gap_agent",
            user_id=UUID(user_id),
            conversation_id=None,
            work_item_id=UUID(work_item_id),
            callback_url=settings.dundun.callback_url,
            payload={"work_item_id": work_item_id},
        )
        request_id: str = str(result["request_id"])
        logger.info(
            "invoke_gap_agent dispatched work_item=%s request_id=%s",
            work_item_id,
            request_id,
        )
        return request_id
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# invoke_quick_action_agent
# ---------------------------------------------------------------------------


async def invoke_quick_action_agent(
    *,
    work_item_id: str,
    user_id: str,
    action_id: str,
    action_type: str,
    section_id: str | None = None,
) -> str:
    """Invoke Dundun's wm_quick_action_agent. Returns the Dundun request_id.

    # TODO: wire into QuickActionService when EP-04 lands.
    # QuickActionService.execute / undo are deferred — requires work_item_sections
    # (EP-04) and undo TTL infra. This function dispatches directly to DundunClient
    # and relies on the callback handler (Phase 3b / EP-04) to process the result.

    # TODO(pg-jobs): crash mid-run = silent failure; move to pg jobs table if reliability needed.
    """
    deps = await _build_deps()
    dundun_client = deps["dundun_client"]
    session = deps.get("_session")
    try:
        from app.config.settings import get_settings
        settings = get_settings()

        payload: dict[str, str] = {
            "action_id": action_id,
            "action_type": action_type,
        }
        if section_id is not None:
            payload["section_id"] = section_id

        result = await dundun_client.invoke_agent(
            agent="wm_quick_action_agent",
            user_id=UUID(user_id),
            conversation_id=None,
            work_item_id=UUID(work_item_id),
            callback_url=settings.dundun.callback_url,
            payload=payload,
        )
        request_id: str = str(result["request_id"])
        logger.info(
            "invoke_quick_action_agent dispatched work_item=%s action_id=%s request_id=%s",
            work_item_id,
            action_id,
            request_id,
        )
        return request_id
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)
