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
