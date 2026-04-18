"""EP-17 — Section lock controller.

Routes:
  POST   /api/v1/sections/{id}/lock                      — acquire
  POST   /api/v1/sections/{id}/lock/heartbeat            — refresh TTL
  DELETE /api/v1/sections/{id}/lock                      — release
  POST   /api/v1/sections/{id}/lock/force-release        — admin force-release
  GET    /api/v1/work-items/{id}/locks                   — list active locks
  POST   /api/v1/sections/{id}/lock/unlock-request       — request lock holder to release
  POST   /api/v1/sections/{id}/lock/respond              — lock holder accepts/declines request
"""
from __future__ import annotations

import logging
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models.lock_unlock_request import (
    AlreadyRespondedError,
    LockUnlockRequest,
)
from app.domain.models.section_lock import (
    DEFAULT_LOCK_TTL_SECONDS,
    LockConflictError,
    SectionLock,
)
from app.infrastructure.persistence.lock_repository_impl import SectionLockRepositoryImpl
from app.infrastructure.persistence.lock_unlock_request_repository_impl import (
    LockUnlockRequestRepositoryImpl,
)
from app.infrastructure.persistence.section_repository_impl import SectionRepositoryImpl
from app.infrastructure.sse.pg_notification_bus import PgNotificationBus
from app.presentation.dependencies import get_current_user, get_scoped_session, get_audit_service
from app.presentation.middleware.auth_middleware import CurrentUser
from app.application.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["locks"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _lock_payload(lock: SectionLock) -> dict[str, Any]:
    return {
        "id": str(lock.id),
        "section_id": str(lock.section_id),
        "work_item_id": str(lock.work_item_id),
        "held_by": str(lock.held_by),
        "acquired_at": lock.acquired_at.isoformat(),
        "heartbeat_at": lock.heartbeat_at.isoformat(),
        "expires_at": lock.expires_at.isoformat(),
    }


@router.post("/sections/{section_id}/lock", status_code=http_status.HTTP_201_CREATED)
async def acquire_lock(
    section_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    section_repo = SectionRepositoryImpl(session)
    section = await section_repo.get(section_id)
    if section is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "section not found", "details": {}}},
        )

    lock_repo = SectionLockRepositoryImpl(session)
    existing = await lock_repo.get(section_id)

    if existing is not None and not existing.is_expired():
        if existing.held_by != current_user.id:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail={
                    "error": {
                        "code": "LOCK_CONFLICT",
                        "message": "section is locked by another user",
                        "details": {"held_by": str(existing.held_by)},
                    }
                },
            )
        # Same user re-acquiring — just refresh TTL
        existing.heartbeat()
        saved = await lock_repo.save(existing)
        return _ok(_lock_payload(saved), "lock refreshed")

    lock = SectionLock.acquire(
        section_id=section_id,
        work_item_id=section.work_item_id,
        held_by=current_user.id,
    )
    saved = await lock_repo.acquire(lock)
    return _ok(_lock_payload(saved), "lock acquired")


@router.post("/sections/{section_id}/lock/heartbeat")
async def heartbeat_lock(
    section_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    lock_repo = SectionLockRepositoryImpl(session)
    lock = await lock_repo.get(section_id)
    if lock is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "lock not found", "details": {}}},
        )
    if lock.held_by != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "LOCK_FORBIDDEN",
                    "message": "lock held by another user",
                    "details": {},
                }
            },
        )
    lock.heartbeat(DEFAULT_LOCK_TTL_SECONDS)
    saved = await lock_repo.save(lock)
    return _ok(_lock_payload(saved), "heartbeat ok")


@router.delete("/sections/{section_id}/lock", status_code=http_status.HTTP_200_OK)
async def release_lock(
    section_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    lock_repo = SectionLockRepositoryImpl(session)
    lock = await lock_repo.get(section_id)
    if lock is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "lock not found", "details": {}}},
        )
    try:
        lock.release(current_user.id)
    except LockConflictError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "LOCK_FORBIDDEN", "message": str(exc), "details": {}}},
        ) from exc
    await lock_repo.delete(section_id)
    return _ok({"section_id": str(section_id)}, "lock released")


@router.post("/sections/{section_id}/lock/force-release", status_code=http_status.HTTP_200_OK)
async def force_release_lock(
    section_id: UUID,
    body: ForceReleaseBody,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
    audit: AuditService = Depends(get_audit_service),
) -> dict[str, Any]:
    # TODO: add admin role check when RBAC lands
    lock_repo = SectionLockRepositoryImpl(session)
    lock = await lock_repo.get(section_id)
    if lock is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": "lock not found", "details": {}}},
        )
    lock.force_release()
    await lock_repo.delete(section_id)
    logger.warning(
        "lock.force_release section=%s by=%s was_held_by=%s",
        section_id,
        current_user.id,
        lock.held_by,
    )
    await audit.log_event(
        category="domain",
        action="force_released_section_lock",
        actor_id=current_user.id,
        entity_type="section",
        entity_id=section_id,
        context={"reason": body.reason},
    )
    return _ok({"section_id": str(section_id)}, "lock force-released")


@router.get("/work-items/{work_item_id}/locks")
async def list_work_item_locks(
    work_item_id: UUID,
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    lock_repo = SectionLockRepositoryImpl(session)
    locks = await lock_repo.get_locks_for_work_item(work_item_id)
    return _ok([_lock_payload(lk) for lk in locks])


# ---------------------------------------------------------------------------
# Unlock-request schemas
# ---------------------------------------------------------------------------


class UnlockRequestBody(BaseModel):
    reason: str = Field(..., min_length=1, max_length=500)


class ForceReleaseBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class RespondBody(BaseModel):
    request_id: UUID
    action: Literal["accept", "decline"]
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_asyncpg_dsn() -> str:
    from app.config.settings import get_settings

    return get_settings().database.url.replace("postgresql+asyncpg://", "postgresql://")


async def _publish_unlock_event(section_id: UUID, payload: dict[str, Any]) -> None:
    try:
        bus = PgNotificationBus(dsn=_get_asyncpg_dsn())
        await bus.publish(f"sse:section:{section_id}", payload)
    except Exception:
        logger.warning("pg_notify failed for section=%s — continuing", section_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/sections/{section_id}/lock/unlock-request",
    status_code=http_status.HTTP_201_CREATED,
)
async def request_unlock(
    section_id: UUID,
    body: UnlockRequestBody,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    """Signal the lock holder that another member wants them to release."""
    lock_repo = SectionLockRepositoryImpl(session)
    lock = await lock_repo.get(section_id)

    if lock is None or lock.is_expired():
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "NO_ACTIVE_LOCK",
                    "message": "no active lock on this section",
                    "details": {},
                }
            },
        )

    if lock.held_by == current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": {
                    "code": "CANNOT_REQUEST_OWN_LOCK",
                    "message": "you cannot request release of your own lock",
                    "details": {},
                }
            },
        )

    request = LockUnlockRequest.create(
        section_id=section_id,
        requester_id=current_user.id,
        reason=body.reason,
    )
    req_repo = LockUnlockRequestRepositoryImpl(session)
    saved = await req_repo.save(request)
    await session.commit()

    await _publish_unlock_event(
        section_id,
        {
            "event": "unlock_requested",
            "request_id": str(saved.id),
            "section_id": str(section_id),
            "requester_id": str(current_user.id),
            "reason": saved.reason,
        },
    )

    return _ok(saved.to_dict(), "unlock request sent")


@router.post("/sections/{section_id}/lock/respond", status_code=http_status.HTTP_200_OK)
async def respond_to_unlock_request(
    section_id: UUID,
    body: RespondBody,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_scoped_session),
) -> dict[str, Any]:
    """Lock holder accepts or declines an unlock request."""
    lock_repo = SectionLockRepositoryImpl(session)
    lock = await lock_repo.get(section_id)

    if lock is None or lock.is_expired():
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "NO_ACTIVE_LOCK",
                    "message": "no active lock on this section",
                    "details": {},
                }
            },
        )

    if lock.held_by != current_user.id:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "LOCK_FORBIDDEN",
                    "message": "only the lock holder can respond to unlock requests",
                    "details": {},
                }
            },
        )

    req_repo = LockUnlockRequestRepositoryImpl(session)
    unlock_request = await req_repo.get(body.request_id)
    if unlock_request is None or unlock_request.section_id != section_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "NOT_FOUND",
                    "message": "unlock request not found",
                    "details": {},
                }
            },
        )

    try:
        if body.action == "accept":
            unlock_request.accept()
            # Release the lock
            lock.release(current_user.id)
            await lock_repo.delete(section_id)
        else:
            unlock_request.decline(body.note)
    except AlreadyRespondedError:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "ALREADY_RESPONDED",
                    "message": "unlock request has already been responded to",
                    "details": {},
                }
            },
        )

    await req_repo.save(unlock_request)
    await session.commit()

    await _publish_unlock_event(
        section_id,
        {
            "event": "unlock_responded",
            "request_id": str(unlock_request.id),
            "section_id": str(section_id),
            "action": body.action,
        },
    )

    return _ok(unlock_request.to_dict(), f"request {body.action}ed")
