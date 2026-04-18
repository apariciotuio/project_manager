"""EP-08 — Notification fan-out and sweep tasks.

fan_out_notification:
  - Receives an event_type + payload dict from the in-process event bus delegate.
  - Calls _build_fan_out_deps() to resolve recipients (monkeypatchable in tests).
  - Builds Notification domain rows per recipient with a deterministic idempotency_key.
  - Calls ExtendedNotificationService.bulk_enqueue (→ bulk_insert_idempotent).

sweep_expired_notifications:
  - Archives read notifications > 30 days old (sets archived_at).
  - Archives actioned notifications > 90 days old (sets archived_at).
  - Triggered via POST /api/v1/internal/jobs/sweep_notifications/run (superadmin).
  - Host cron hits that endpoint daily at 01:00 UTC.

_build_*_deps() deferred imports avoid the lru_cache trap.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.domain.models.team import Notification

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fan-out
# ---------------------------------------------------------------------------


async def _build_fan_out_deps(
    event_type: str, payload: dict[str, Any]
) -> dict[str, Any]:
    """Build ExtendedNotificationService + resolve recipients.

    Deferred imports avoid lru_cache trap (see project_settings_lru_cache_trap.md).
    Recipients are resolved from the payload. For team events the payload must
    include `team_member_ids`; for direct events `recipient_id` suffices.
    """
    from app.config.settings import get_settings
    from app.application.services.notification_service import ExtendedNotificationService
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.team_repository_impl import NotificationRepositoryImpl

    get_settings()  # ensure settings initialised

    factory = get_session_factory()
    session = factory()
    await session.__aenter__()

    repo = NotificationRepositoryImpl(session)
    svc = ExtendedNotificationService(notification_repo=repo)
    svc._session = session  # type: ignore[attr-defined]  # used for commit/close

    # Recipient resolution: prefer explicit list, fall back to single recipient_id.
    recipients: list[UUID] = []
    if "team_member_ids" in payload and payload["team_member_ids"]:
        recipients = [UUID(rid) for rid in payload["team_member_ids"]]
    elif "recipient_id" in payload and payload["recipient_id"]:
        recipients = [UUID(payload["recipient_id"])]

    return {"svc": svc, "recipients": recipients}


async def _run_fan_out(
    *,
    event_type: str,
    payload: dict[str, Any],
    recipients: list[UUID],
    svc: Any,
) -> dict[str, int]:
    """Core fan-out logic (extracted for testability).

    Builds one Notification per recipient with a deterministic idempotency_key:
      f"{event_type}:{source_id}:{recipient_id}"
    Calls svc.bulk_enqueue → bulk_insert_idempotent (ON CONFLICT DO NOTHING).
    """
    if not recipients:
        logger.info("notification_fan_out: no recipients for event_type=%s", event_type)
        return {"inserted": 0}

    workspace_id = UUID(payload["workspace_id"])
    source_id = payload["source_id"]
    subject_type = payload.get("subject_type", "work_item")
    subject_id = UUID(payload["subject_id"])
    deeplink = payload.get("deeplink", f"/items/{subject_id}")
    actor_id_raw = payload.get("actor_id")
    actor_id = UUID(actor_id_raw) if actor_id_raw else None
    extra: dict[str, Any] = payload.get("extra") or {}

    notifications: list[Notification] = []
    for recipient_id in recipients:
        ikey = f"{event_type}:{source_id}:{recipient_id}"
        n = Notification.create(
            workspace_id=workspace_id,
            recipient_id=recipient_id,
            type=event_type,
            subject_type=subject_type,
            subject_id=subject_id,
            deeplink=deeplink,
            idempotency_key=ikey,
            actor_id=actor_id,
            extra=extra,
        )
        notifications.append(n)

    persisted = await svc.bulk_enqueue(notifications=notifications)
    count = len(persisted)

    logger.info(
        "notification_fan_out: event_type=%s source_id=%s inserted=%d",
        event_type,
        source_id,
        count,
    )
    return {"inserted": count}


async def fan_out_notification(
    *,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, int]:
    """Fan out a domain event to per-recipient notification rows.

    Args:
        event_type: e.g. "review.requested", "assignment.changed"
        payload: dict with workspace_id, source_id, subject_type, subject_id,
                 deeplink, actor_id (nullable), extra (dict), and optionally
                 team_member_ids (list[str]) or recipient_id (str).
    """
    deps = await _build_fan_out_deps(event_type, payload)
    svc = deps["svc"]
    recipients: list[UUID] = deps["recipients"]
    session = getattr(svc, "_session", None)
    try:
        result = await _run_fan_out(
            event_type=event_type,
            payload=payload,
            recipients=recipients,
            svc=svc,
        )
        if session is not None:
            await session.commit()
        return result
    except Exception:
        if session is not None:
            await session.rollback()
        raise
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


async def _build_sweep_deps() -> dict[str, Any]:
    """Build DB access for sweep task (deferred imports, monkeypatchable)."""
    from app.config.settings import get_settings
    from app.infrastructure.persistence.database import get_session_factory
    from app.infrastructure.persistence.team_repository_impl import NotificationRepositoryImpl

    get_settings()

    factory = get_session_factory()
    session = factory()
    await session.__aenter__()
    repo = NotificationRepositoryImpl(session)
    repo._session_obj = session  # type: ignore[attr-defined]
    return {"repo": repo}


async def _run_sweep() -> dict[str, int]:
    """Archive stale notifications.

    - Read > 30 days old → archived_at set.
    - Actioned > 90 days old → archived_at set.
    """
    deps = await _build_sweep_deps()
    repo = deps["repo"]
    session = getattr(repo, "_session_obj", None)

    now = datetime.now(UTC)
    read_threshold = now - timedelta(days=30)
    actioned_threshold = now - timedelta(days=90)

    try:
        result = await repo.archive_stale(
            read_before=read_threshold,
            actioned_before=actioned_threshold,
            now=now,
        )
        if session is not None:
            await session.commit()
    except Exception:
        if session is not None:
            await session.rollback()
        raise
    finally:
        if session is not None:
            await session.__aexit__(None, None, None)

    logger.info(
        "notification_sweep: archived_read=%d archived_actioned=%d",
        result.get("archived_read", 0),
        result.get("archived_actioned", 0),
    )
    return result


async def sweep_expired_notifications() -> dict[str, int]:
    """Archive stale notifications.

    - Marks read > 30 days as archived (sets archived_at).
    - Marks actioned > 90 days as archived (sets archived_at).

    Triggered via POST /api/v1/internal/jobs/sweep_notifications/run (superadmin).
    Host cron hits that endpoint daily at 01:00 UTC.
    """
    return await _run_sweep()
