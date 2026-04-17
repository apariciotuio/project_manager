"""In-process async event bus.

Fire-and-forget: emit() never raises. Handler exceptions are logged and execution continues.
Thread-safety: not required — asyncio single-threaded.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    """Marker base class for all domain events."""


EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[type[Event], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[Event], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def emit(self, event: Event) -> None:
        handlers = self._handlers.get(type(event), [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception:
                logger.error(
                    "event handler failed: event=%s handler=%s",
                    event.__class__.__name__,
                    handler.__qualname__,
                    exc_info=True,
                )


# ---------------------------------------------------------------------------
# Global shared bus — singleton registered once at startup.
#
# All domain services that emit events (WorkItemService, ReviewService, etc.)
# should use this shared instance so that subscribers (timeline, notifications)
# are invoked. Subscribers are registered in register_event_subscribers()
# called from create_app().
# ---------------------------------------------------------------------------

_global_bus: EventBus | None = None


def get_global_bus() -> EventBus:
    """Return the process-wide shared EventBus, creating it on first call."""
    global _global_bus
    if _global_bus is None:
        _global_bus = EventBus()
    return _global_bus


def reset_global_bus() -> None:
    """Reset the global bus. Only for use in tests."""
    global _global_bus
    _global_bus = None
