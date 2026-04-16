from celery import Celery
from celery.schedules import crontab

from app.config.settings import get_settings


def _create_celery() -> Celery:
    settings = get_settings()

    app = Celery(
        "wmp",
        broker=settings.celery.broker_url,
        backend=settings.celery.result_backend,
    )

    app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_always_eager=settings.celery.task_always_eager,
        task_queues={
            "default": {"exchange": "default", "routing_key": "default"},
            "dundun": {"exchange": "dundun", "routing_key": "dundun"},
            "puppet_sync": {"exchange": "puppet_sync", "routing_key": "puppet_sync"},
        },
        task_default_queue="default",
        task_routes={
            "app.infrastructure.tasks.dundun.*": {"queue": "dundun"},
            "app.infrastructure.tasks.puppet.*": {"queue": "puppet_sync"},
        },
        beat_schedule={
            "cleanup-expired-sessions-daily": {
                "task": (
                    "app.infrastructure.jobs.session_cleanup.cleanup_expired_sessions"
                ),
                "schedule": crontab(hour=3, minute=15),
            },
            "cleanup-expired-oauth-states-every-10m": {
                "task": (
                    "app.infrastructure.jobs.oauth_state_cleanup"
                    ".cleanup_expired_oauth_states"
                ),
                "schedule": crontab(minute="*/10"),
            },
            "expire-work-item-drafts-daily": {
                "task": (
                    "app.infrastructure.jobs.expire_drafts_task"
                    ".expire_work_item_drafts"
                ),
                "schedule": crontab(hour=2, minute=0),
            },
        },
    )

    app.autodiscover_tasks(["app.infrastructure.jobs", "app.infrastructure.tasks"])
    return app


celery_app = _create_celery()
