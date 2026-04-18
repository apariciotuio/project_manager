"""Internal jobs controller — superadmin-only job triggers.

Replaces Celery Beat scheduled tasks. Host cron calls these endpoints:

  Job name                        Schedule (UTC)    Replaces beat key
  cleanup_expired_sessions        daily 03:15       cleanup-expired-sessions-daily
  cleanup_expired_oauth_states    every 10m         cleanup-expired-oauth-states-every-10m
  expire_work_item_drafts         daily 02:00       expire-work-item-drafts-daily
  sweep_notifications             daily 01:00       (was registered in notification_tasks)
  drain_puppet_outbox             on-demand         (was triggered by beat or tests)
  process_puppet_ingest           on-demand         (was triggered by beat or tests)

Auth: requires is_superadmin in JWT. 403 for anything else.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi import status as http_status

from app.presentation.dependencies import get_current_user
from app.presentation.middleware.auth_middleware import CurrentUser
from app.presentation.rate_limit import auth_limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/jobs", tags=["internal-jobs"])

# Registry of runnable jobs — name → async callable
_JOB_REGISTRY: dict[str, Any] = {}


def _register_jobs() -> None:
    """Populate registry lazily to avoid circular imports at module load."""
    from app.infrastructure.jobs.expire_drafts_task import expire_work_item_drafts
    from app.infrastructure.jobs.oauth_state_cleanup import cleanup_expired_oauth_states
    from app.infrastructure.jobs.session_cleanup import cleanup_expired_sessions
    from app.infrastructure.tasks.notification_tasks import sweep_expired_notifications
    from app.infrastructure.tasks.puppet_ingest_tasks import process_puppet_ingest
    from app.infrastructure.tasks.puppet_sync_tasks import drain_puppet_outbox

    _JOB_REGISTRY.update(
        {
            "cleanup_expired_sessions": cleanup_expired_sessions,
            "cleanup_expired_oauth_states": cleanup_expired_oauth_states,
            "expire_work_item_drafts": expire_work_item_drafts,
            "sweep_notifications": sweep_expired_notifications,
            "drain_puppet_outbox": drain_puppet_outbox,
            "process_puppet_ingest": process_puppet_ingest,
        }
    )


_register_jobs()


async def _require_superadmin(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={
                "error": {
                    "code": "SUPERADMIN_REQUIRED",
                    "message": "superadmin required",
                    "details": {},
                }
            },
        )
    return current_user


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


@router.post("/{name}/run")
@auth_limiter.limit("5/minute")
async def run_job(
    request: Request,
    name: str,
    _current_user: CurrentUser = Depends(_require_superadmin),
) -> dict[str, Any]:
    """Trigger a background maintenance job synchronously.

    Returns the job result. For cron use, host scheduler calls this endpoint.
    """
    fn = _JOB_REGISTRY.get(name)
    if fn is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "JOB_NOT_FOUND",
                    "message": f"unknown job: {name}",
                    "details": {"available": sorted(_JOB_REGISTRY.keys())},
                }
            },
        )

    logger.info("internal_job.start name=%s user=%s", name, _current_user.id)
    try:
        result = await fn()
        logger.info("internal_job.done name=%s result=%s", name, result)
    except Exception as exc:
        logger.error("internal_job.failed name=%s error=%s", name, exc, exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": {
                    "code": "JOB_FAILED",
                    "message": str(exc),
                    "details": {},
                }
            },
        ) from exc

    return _ok({"job": name, "result": result})


@router.get("/")
async def list_jobs(
    _current_user: CurrentUser = Depends(_require_superadmin),
) -> dict[str, Any]:
    """List available job names."""
    return _ok({"jobs": sorted(_JOB_REGISTRY.keys())})
