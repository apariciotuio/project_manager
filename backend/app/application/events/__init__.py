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
        from app.infrastructure.persistence.database import get_session_factory

        # Pass the session factory directly so each handler owns the full
        # open→write→commit→close lifecycle.  The old pattern of returning
        # a service from inside an async-with block closed the session before
        # the service was used, leaving connections idle-in-transaction.
        register_timeline_subscribers(bus, get_session_factory())
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

    # EP-22 — Chat primer on work item creation
    try:
        # Resolve callback_url at registration time; deferred import per lru_cache trap.
        from app.config.settings import get_settings

        _s = get_settings()
        _callback_url = _s.dundun.callback_url

        # Build a shared stateless proxy that creates fresh DB sessions per event.
        # Following the same pattern as _NotificationProxy above.
        class _ChatPrimerProxy:
            async def handle(self, event: object) -> None:
                from app.application.events.chat_primer_subscriber import (
                    make_chat_primer_handler,
                )
                from app.application.services.conversation_service import ConversationService
                from app.infrastructure.persistence.conversation_thread_repository_impl import (
                    ConversationThreadRepositoryImpl,
                )
                from app.infrastructure.persistence.database import get_session_factory
                from app.infrastructure.persistence.section_repository_impl import (
                    SectionRepositoryImpl,
                )
                from app.infrastructure.persistence.work_item_repository_impl import (
                    WorkItemRepositoryImpl,
                )
                from app.presentation.dependencies import get_dundun_client

                factory = get_session_factory()
                async with factory() as session:
                    try:
                        w_repo = WorkItemRepositoryImpl(session)
                        s_repo = SectionRepositoryImpl(session)
                        t_repo = ConversationThreadRepositoryImpl(session)
                        dundun = get_dundun_client()
                        svc = ConversationService(
                            thread_repo=t_repo,
                            dundun_client=dundun,
                            section_repo=s_repo,
                        )
                        handler = make_chat_primer_handler(
                            work_item_repo=w_repo,
                            thread_repo=t_repo,
                            conversation_svc=svc,
                            dundun_client=dundun,
                            callback_url=_callback_url,
                            section_repo=s_repo,
                        )
                        await handler(event)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                        raise

        from app.application.events.events import WorkItemCreatedEvent as _WICreatedEvent

        _primer_proxy = _ChatPrimerProxy()
        bus.subscribe(_WICreatedEvent, _primer_proxy.handle)
        logger.info("register_event_subscribers: chat_primer subscriber registered")
    except Exception:
        logger.exception(
            "register_event_subscribers: failed to register chat_primer subscriber"
        )
