"""Dundun async callback controller — EP-03 Phase 3b + EP-04 spec-gen + EP-05 breakdown.

Dundun POSTs agent results here after async invocation.
Authentication is HMAC-SHA256 over the raw request body using the shared
DUNDUN_CALLBACK_SECRET.  No JWT / no get_current_user.

POST /api/v1/dundun/callback

Agents handled:
  wm_suggestion_agent  — EP-03
  wm_gap_agent         — EP-03
  wm_spec_gen_agent    — EP-04 (upserts sections, invalidates completeness cache)
  wm_breakdown_agent   — EP-05 (creates task nodes from LLM breakdown)
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.domain.models.assistant_suggestion import AssistantSuggestion, SuggestionStatus
from app.domain.models.gap_finding import GapSeverity, StoredGapFinding
from app.domain.models.section import Section
from app.domain.models.section_catalog import catalog_for
from app.domain.models.section_type import GenerationSource, SectionType
from app.infrastructure.adapters.dundun_callback_verifier import verify_dundun_signature
from app.infrastructure.persistence.assistant_suggestion_repository_impl import (
    AssistantSuggestionRepositoryImpl,
)
from app.infrastructure.persistence.gap_finding_repository_impl import (
    GapFindingRepositoryImpl,
)
from app.infrastructure.persistence.models.orm import WorkItemORM
from app.infrastructure.persistence.section_repository_impl import (
    SectionRepositoryImpl,
    SectionVersionRepositoryImpl,
)
from app.infrastructure.persistence.session_context import with_workspace
from app.presentation.dependencies import get_callback_session
from app.presentation.schemas.dundun_callback_schemas import DundunCallbackRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dundun"])

_SUGGESTION_EXPIRES_HOURS = 24

_INVALID_SIG_RESPONSE = JSONResponse(
    status_code=http_status.HTTP_401_UNAUTHORIZED,
    content={
        "error": {
            "code": "INVALID_SIGNATURE",
            "message": "invalid or missing signature",
            "details": {},
        }
    },
)


def _ok(agent: str, count: int, note: str = "") -> JSONResponse:
    return JSONResponse(
        status_code=http_status.HTTP_200_OK,
        content={
            "data": {"processed": True, "agent": agent, "count": count},
            "message": note or "processed",
        },
    )


@router.post("/dundun/callback")
async def dundun_callback(
    request: Request,
    session: AsyncSession = Depends(get_callback_session),
) -> JSONResponse:
    # Build both repos off the same session so RLS SET LOCAL applies to both
    # and the two writes share one transaction.
    suggestion_repo = AssistantSuggestionRepositoryImpl(session)
    gap_repo = GapFindingRepositoryImpl(session)
    # 1. Read raw body — must happen before Pydantic parsing
    raw_body = await request.body()

    # 2. Verify HMAC signature
    header_sig = request.headers.get("X-Dundun-Signature", "")
    if not header_sig:
        return _INVALID_SIG_RESPONSE

    settings = get_settings()
    if not verify_dundun_signature(raw_body, header_sig, settings.dundun.callback_secret):
        return _INVALID_SIG_RESPONSE

    # 3. Parse body
    try:
        payload = DundunCallbackRequest.model_validate_json(raw_body)
    except Exception:
        return JSONResponse(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "invalid payload",
                    "details": {},
                }
            },
        )

    # 4. status=error — log and return 200, nothing persisted
    if payload.status == "error":
        logger.warning(
            "dundun_callback: agent=%s request_id=%s error=%s",
            payload.agent,
            payload.request_id,
            payload.error_message,
        )
        return _ok(payload.agent, 0, "error logged")

    # 5. Route by agent
    if payload.agent == "wm_suggestion_agent":
        return await _handle_suggestion(payload, session, suggestion_repo)

    if payload.agent == "wm_gap_agent":
        return await _handle_gap(payload, session, gap_repo)

    if payload.agent == "wm_spec_gen_agent":
        return await _handle_spec_gen(payload, session)

    if payload.agent == "wm_breakdown_agent":
        return await _handle_breakdown_callback(payload, session)

    # wm_quick_action_agent — deferred
    return JSONResponse(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": "quick_action callbacks are not yet implemented",
                "details": {},
            }
        },
    )


async def _resolve_workspace_id(session: AsyncSession, work_item_id: UUID) -> UUID:
    """Look up a work item's workspace_id and SET LOCAL for RLS.

    The Dundun callback runs outside user auth, so there's no workspace context
    from a JWT. We derive it from the referenced work item. Raises 422 if the
    work item does not exist.
    """
    stmt = select(WorkItemORM.workspace_id).where(WorkItemORM.id == work_item_id)
    workspace_id = (await session.execute(stmt)).scalar_one_or_none()
    if workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "WORK_ITEM_NOT_FOUND",
                    "message": f"work_item {work_item_id} not found",
                    "details": {},
                }
            },
        )
    await with_workspace(session, workspace_id)
    return workspace_id


async def _handle_suggestion(
    payload: DundunCallbackRequest,
    session: AsyncSession,
    repo: AssistantSuggestionRepositoryImpl,
) -> JSONResponse:
    """Persist suggestion rows for wm_suggestion_agent callbacks."""
    # Idempotency: already processed?
    existing = await repo.get_by_dundun_request_id(payload.request_id)
    if existing:
        logger.info(
            "dundun_callback: duplicate suggestion request_id=%s (already processed, %d rows)",
            payload.request_id,
            len(existing),
        )
        return _ok(payload.agent, len(existing), "duplicate request_id — already processed")

    items = payload.suggestions or []
    if not items:
        return _ok(payload.agent, 0, "no suggestions in payload")

    if payload.work_item_id is None or payload.user_id is None or payload.batch_id is None:
        logger.warning(
            "dundun_callback: suggestion missing required ids request_id=%s wi=%s batch=%s user=%s",
            payload.request_id,
            payload.work_item_id,
            payload.batch_id,
            payload.user_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id, batch_id and user_id are required for suggestions",
                    "details": {},
                }
            },
        )
    work_item_id: UUID = payload.work_item_id
    batch_id: UUID = payload.batch_id
    created_by: UUID = payload.user_id
    workspace_id = await _resolve_workspace_id(session, work_item_id)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=_SUGGESTION_EXPIRES_HOURS)

    # Resolve version_number_target from the versioning repo (EP-07).
    # latest.version_number + 1 is the version this suggestion targets.
    # Falls back to 1 when no versions exist yet (fresh work item).
    from app.infrastructure.persistence.work_item_version_repository_impl import (
        WorkItemVersionRepositoryImpl,
    )
    version_repo = WorkItemVersionRepositoryImpl(session)
    latest_version = await version_repo.get_latest(work_item_id, workspace_id)
    version_number_target = (latest_version.version_number if latest_version else 0) + 1

    suggestions = [
        AssistantSuggestion(
            id=uuid4(),
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            thread_id=None,
            section_id=item.section_id,
            proposed_content=item.proposed_content,
            current_content=item.current_content,
            rationale=item.rationale,
            status=SuggestionStatus.PENDING,
            version_number_target=version_number_target,
            batch_id=batch_id,
            dundun_request_id=payload.request_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        for item in items
    ]

    persisted = await repo.create_batch(suggestions)
    logger.info(
        "dundun_callback: persisted %d suggestions for work_item=%s batch=%s request_id=%s",
        len(persisted),
        work_item_id,
        batch_id,
        payload.request_id,
    )
    return _ok(payload.agent, len(persisted))


async def _handle_gap(
    payload: DundunCallbackRequest,
    session: AsyncSession,
    repo: GapFindingRepositoryImpl,
) -> JSONResponse:
    """Persist gap findings for wm_gap_agent callbacks."""
    if payload.work_item_id is None:
        logger.warning(
            "dundun_callback: gap missing work_item_id request_id=%s",
            payload.request_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id is required for gap findings",
                    "details": {},
                }
            },
        )
    work_item_id: UUID = payload.work_item_id
    workspace_id = await _resolve_workspace_id(session, work_item_id)
    now = datetime.now(UTC)

    # Idempotency: check if this request_id was already processed
    existing = await repo.get_active_for_work_item(work_item_id, source="dundun")
    already_for_request = [f for f in existing if f.dundun_request_id == payload.request_id]
    if already_for_request:
        logger.info(
            "dundun_callback: duplicate gap request_id=%s (already processed, %d rows)",
            payload.request_id,
            len(already_for_request),
        )
        return _ok(
            payload.agent,
            len(already_for_request),
            "duplicate request_id — already processed",
        )

    # Invalidate previous Dundun findings for this work item before inserting fresh ones
    await repo.invalidate_for_work_item(work_item_id, now, source="dundun")

    raw_findings = payload.gap_findings or []
    if not raw_findings:
        return _ok(payload.agent, 0, "no gap findings in payload")

    findings = [
        StoredGapFinding(
            id=uuid4(),
            workspace_id=workspace_id,
            work_item_id=work_item_id,
            dimension=f.dimension,
            severity=GapSeverity(f.severity),
            message=f.message,
            source="dundun",
            dundun_request_id=payload.request_id,
            created_at=now,
            invalidated_at=None,
        )
        for f in raw_findings
    ]

    persisted = await repo.insert_many(findings)
    logger.info(
        "dundun_callback: persisted %d gap findings for work_item=%s request_id=%s",
        len(persisted),
        work_item_id,
        payload.request_id,
    )
    return _ok(payload.agent, len(persisted))


async def _handle_spec_gen(
    payload: DundunCallbackRequest,
    session: AsyncSession,
) -> JSONResponse:
    """Upsert sections returned by wm_spec_gen_agent and invalidate completeness cache.

    Each item in payload.sections carries a `dimension` (matching SectionType enum values)
    and `content`. Unknown dimension values are skipped with a warning — the agent may
    return sections that don't exist in the current catalog.
    """
    if payload.work_item_id is None:
        logger.warning(
            "dundun_callback: spec_gen missing work_item_id request_id=%s",
            payload.request_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id is required for spec_gen",
                    "details": {},
                }
            },
        )

    work_item_id: UUID = payload.work_item_id
    await _resolve_workspace_id(session, work_item_id)

    raw_sections = payload.sections or []
    if not raw_sections:
        return _ok(payload.agent, 0, "no sections in payload")

    section_repo = SectionRepositoryImpl(session)
    version_repo = SectionVersionRepositoryImpl(session)

    # Fetch all existing sections for the work item (one query)
    existing: list[Section] = await section_repo.get_by_work_item(work_item_id)
    existing_by_type: dict[str, Section] = {s.section_type.value: s for s in existing}

    # Fetch work item metadata: type + creator_id (used as actor for FK integrity)
    # The callback has no user auth — we attribute writes to the work item creator.
    stmt = select(WorkItemORM.type, WorkItemORM.creator_id).where(WorkItemORM.id == work_item_id)
    row = (await session.execute(stmt)).one_or_none()
    work_item_type_str = row[0] if row else None
    # FK-safe actor: work item creator always exists; falls back to a random UUID only
    # if the work item somehow has no creator (should never happen given DB constraints).
    agent_actor_id: UUID = row[1] if row else uuid4()

    saved = 0
    skipped = 0

    for item in raw_sections:
        # Validate dimension is a known SectionType
        try:
            section_type = SectionType(item.dimension)
        except ValueError:
            logger.warning(
                "dundun_callback: spec_gen unknown dimension=%s work_item=%s — skipping",
                item.dimension,
                work_item_id,
            )
            skipped += 1
            continue

        if section_type.value in existing_by_type:
            # Update existing section
            section = existing_by_type[section_type.value]
            section.update_content(item.content, agent_actor_id, source=GenerationSource.LLM)
            await section_repo.save(section)
            await version_repo.append(section, agent_actor_id)
        else:
            # Create a new section with display_order from catalog if available
            display_order = 99  # fallback
            if work_item_type_str is not None:
                try:
                    from app.domain.value_objects.work_item_type import WorkItemType
                    wt = WorkItemType(work_item_type_str)
                    configs = catalog_for(wt)
                    for cfg in configs:
                        if cfg.section_type == section_type:
                            display_order = cfg.display_order
                            break
                except (ValueError, KeyError):
                    pass

            section = Section.create(
                work_item_id=work_item_id,
                section_type=section_type,
                display_order=display_order,
                is_required=False,
                created_by=agent_actor_id,
                content=item.content,
                generation_source=GenerationSource.LLM,
            )
            await section_repo.save(section)
            await version_repo.append(section, agent_actor_id)

        saved += 1

    # Invalidate completeness cache so the next GET /completeness recomputes.
    # The callback has no FastAPI DI cache dep, so we build it directly from settings.
    # On cache connection failure we log a warning and continue — stale data for up
    # to 60s is acceptable for an async background callback.
    try:
        _settings = get_settings()
        cache_key = f"completeness:{work_item_id}"
        if _settings.redis.use_fake:
            from app.presentation.dependencies import _IN_MEMORY_CACHE as _fake_cache
            if _fake_cache is not None:
                await _fake_cache.delete(cache_key)
        else:
            from app.infrastructure.adapters.redis_cache_adapter import RedisCacheAdapter
            _rc = RedisCacheAdapter(url=_settings.redis.url)
            try:
                await _rc.delete(cache_key)
            finally:
                await _rc.close()
    except Exception as _cache_err:
        logger.warning(
            "dundun_callback: spec_gen cache invalidation failed work_item=%s err=%s",
            work_item_id,
            _cache_err,
        )

    logger.info(
        "dundun_callback: spec_gen upserted=%d skipped=%d work_item=%s request_id=%s",
        saved,
        skipped,
        work_item_id,
        payload.request_id,
    )
    return _ok(payload.agent, saved)


# ---------------------------------------------------------------------------
# EP-05 — wm_breakdown_agent handler
# ---------------------------------------------------------------------------


async def _handle_breakdown(
    *,
    session: AsyncSession,
    work_item_id: UUID,
    workspace_id: UUID,
    breakdown: list[dict],
    request_id: str,
    task_service: object,
    actor_id: UUID,
) -> dict:
    """Pure breakdown logic — extracted for unit testing.

    Args:
        session: async DB session (unused directly; provided for symmetry/future use)
        work_item_id: target work item
        workspace_id: resolved workspace (RLS already applied before this call)
        breakdown: list of dicts with 'title', optional 'parent_title', optional 'description'
        request_id: Dundun request id (for idempotency logging only here)
        task_service: TaskService instance
        actor_id: UUID to attribute created nodes to

    Returns:
        dict with created_count and skipped_count
    """
    # title → created TaskNode, built incrementally so forward refs in the
    # breakdown list resolve to nodes created earlier in this batch.
    title_to_node: dict[str, object] = {}
    created_count = 0
    skipped_count = 0

    for i, item in enumerate(breakdown):
        title = item.get("title") if isinstance(item, dict) else getattr(item, "title", None)
        if not title:
            skipped_count += 1
            continue

        parent_title = (
            item.get("parent_title") if isinstance(item, dict) else getattr(item, "parent_title", None)
        )
        description = (
            item.get("description", "") if isinstance(item, dict) else getattr(item, "description", "")
        ) or ""

        # Resolve parent: look up in title_to_node built so far.
        # Unknown parent_title → fall back to root (parent_id=None).
        parent_id: UUID | None = None
        if parent_title:
            parent_node = title_to_node.get(parent_title)
            if parent_node is not None:
                parent_id = parent_node.id  # type: ignore[attr-defined]
            else:
                logger.warning(
                    "dundun_callback: breakdown parent_title=%r not found in batch — "
                    "falling back to root for title=%r request_id=%s",
                    parent_title,
                    title,
                    request_id,
                )

        node = await task_service.create_node(  # type: ignore[union-attr]
            work_item_id=work_item_id,
            parent_id=parent_id,
            title=title,
            display_order=i,
            actor_id=actor_id,
            description=description,
        )
        title_to_node[title] = node
        created_count += 1

    return {"created_count": created_count, "skipped_count": skipped_count}


async def _handle_breakdown_callback(
    payload: DundunCallbackRequest,
    session: AsyncSession,
) -> JSONResponse:
    """Route handler for wm_breakdown_agent — EP-05.

    Idempotency: Dundun guarantees at-least-once delivery. We rely on
    request_id uniqueness logged at INFO level. A re-delivered request_id
    produces duplicate task nodes — acceptable at current scale; callers
    should check task count before triggering generate again.
    Future: store processed request_ids in a lightweight table (migration 0121).
    """
    if payload.work_item_id is None:
        logger.warning(
            "dundun_callback: breakdown missing work_item_id request_id=%s",
            payload.request_id,
        )
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "MISSING_IDS",
                    "message": "work_item_id is required for breakdown",
                    "details": {},
                }
            },
        )

    work_item_id: UUID = payload.work_item_id
    workspace_id = await _resolve_workspace_id(session, work_item_id)

    breakdown_items = payload.breakdown or []
    if not breakdown_items:
        return _ok(payload.agent, 0, "no breakdown items in payload")

    # Fetch work item creator as actor (callback has no user auth)
    actor_actor_id: UUID
    stmt = select(WorkItemORM.creator_id).where(WorkItemORM.id == work_item_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        actor_actor_id = uuid4()
    else:
        actor_actor_id = row

    from app.application.services.task_service import TaskService
    from app.infrastructure.persistence.task_node_repository_impl import (
        TaskDependencyRepositoryImpl,
        TaskNodeRepositoryImpl,
        TaskSectionLinkRepositoryImpl,
    )

    task_service = TaskService(
        node_repo=TaskNodeRepositoryImpl(session),
        dep_repo=TaskDependencyRepositoryImpl(session),
        link_repo=TaskSectionLinkRepositoryImpl(session),
    )

    result = await _handle_breakdown(
        session=session,
        work_item_id=work_item_id,
        workspace_id=workspace_id,
        breakdown=[
            {"title": item.title, "parent_title": item.parent_title, "description": item.description}
            for item in breakdown_items
        ],
        request_id=payload.request_id,
        task_service=task_service,
        actor_id=actor_actor_id,
    )

    logger.info(
        "dundun_callback: breakdown created=%d skipped=%d work_item=%s request_id=%s",
        result["created_count"],
        result["skipped_count"],
        work_item_id,
        payload.request_id,
    )
    return _ok(payload.agent, result["created_count"],
               f"created={result['created_count']} skipped={result['skipped_count']}")
