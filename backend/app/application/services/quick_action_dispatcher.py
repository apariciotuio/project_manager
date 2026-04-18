"""EP-08 B6.4a — QuickActionDispatcher.

Maps action types to downstream service calls.  NotificationService depends
ONLY on QuickActionDispatcher — not on ReviewResponseService, WorkItemService,
etc. (SD-4 from backend_review.md).

Handlers are registered at app startup via register().  The dispatcher itself
is a plain dict-based registry — no ABCs, no factories, no indirection.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

_Handler = Callable[[UUID, UUID], Awaitable[dict[str, Any]]]


class QuickActionDispatcher:
    """Dispatch quick actions from the inbox to downstream services.

    Usage:
        dispatcher = QuickActionDispatcher()
        dispatcher.register("approve", approve_handler)
        dispatcher.register("reject", reject_handler)

        result = await dispatcher.dispatch(
            action_type="approve",
            subject_id=review_id,
            actor_id=user_id,
        )
    """

    def __init__(self) -> None:
        self._handlers: dict[str, _Handler] = {}

    def register(self, action_type: str, handler: _Handler) -> None:
        """Register a handler for an action type.

        Overwrites any existing handler for the same type.
        """
        self._handlers[action_type] = handler

    async def dispatch(
        self,
        *,
        action_type: str,
        subject_id: UUID,
        actor_id: UUID,
    ) -> dict[str, Any]:
        """Execute the handler for *action_type*.

        Raises:
            ValueError: when no handler is registered for *action_type*.
        """
        handler = self._handlers.get(action_type)
        if handler is None:
            raise ValueError(
                f"unknown action type: {action_type!r}. Registered: {list(self._handlers)}"
            )
        logger.info(
            "quick_action.dispatch action=%s subject=%s actor=%s",
            action_type,
            subject_id,
            actor_id,
        )
        return await handler(subject_id, actor_id)
