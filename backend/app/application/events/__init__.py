"""EP-08 — Event subscriber registration.

Call register_event_subscribers(bus) once at application startup to wire all
domain event handlers (timeline, notifications, etc.) to the shared EventBus.
"""
from __future__ import annotations

import logging

from app.application.events.event_bus import EventBus

logger = logging.getLogger(__name__)


def register_event_subscribers(bus: EventBus) -> None:
    """Register all event subscribers on the given EventBus.

    Called from create_app() after the global bus is initialised. Subscribers
    are registered once; handlers are invoked for every emitted event.
    """
    # EP-07 — Timeline subscribers
    try:
        from app.application.events.timeline_subscriber import (
            register_timeline_subscribers,
        )
        from app.application.services.timeline_service import TimelineService
        from app.infrastructure.persistence.database import get_session_factory
        from app.infrastructure.persistence.timeline_repository_impl import (
            TimelineEventRepositoryImpl,
        )

        async def _get_timeline_svc() -> TimelineService:
            factory = get_session_factory()
            async with factory() as session:
                return TimelineService(
                    timeline_repo=TimelineEventRepositoryImpl(session)
                )

        register_timeline_subscribers(bus, _get_timeline_svc)
        logger.info("register_event_subscribers: timeline subscribers registered")
    except Exception:
        logger.exception(
            "register_event_subscribers: failed to register timeline subscribers"
        )

    # EP-08 — Notification subscribers
    try:
        from app.application.events.notification_subscriber import (
            register_notification_subscribers,
        )

        # Use a simple callable-duck-type: the subscriber calls `svc.enqueue(...)`.
        # We build a thin object that wraps session creation around each enqueue call.
        # Deferred imports per MEMORY.md lru_cache trap.
        class _NotificationProxy:
            """Duck-typed NotificationService proxy with per-call session management."""

            async def enqueue(self, **kwargs: object) -> object:
                from app.application.services.team_service import NotificationService
                from app.infrastructure.persistence.database import get_session_factory
                from app.infrastructure.persistence.team_repository_impl import (
                    NotificationRepositoryImpl,
                )

                factory = get_session_factory()
                async with factory() as session:
                    try:
                        repo = NotificationRepositoryImpl(session)
                        svc = NotificationService(notification_repo=repo)
                        result = await svc.enqueue(**kwargs)
                        await session.commit()
                        return result
                    except Exception:
                        await session.rollback()
                        raise

        _proxy = _NotificationProxy()

        async def _get_notification_svc() -> _NotificationProxy:
            return _proxy

        register_notification_subscribers(bus, _get_notification_svc)
        logger.info("register_event_subscribers: notification subscribers registered")
    except Exception:
        logger.exception(
            "register_event_subscribers: failed to register notification subscribers"
        )

    # EP-10 — Validation template auto-seed on work item creation
    try:
        from app.application.events.validation_template_subscriber import (
            register_validation_template_subscribers,
        )

        register_validation_template_subscribers(bus)
        logger.info(
            "register_event_subscribers: validation template subscriber registered"
        )
    except Exception:
        logger.exception(
            "register_event_subscribers: failed to register validation template subscriber"
        )
