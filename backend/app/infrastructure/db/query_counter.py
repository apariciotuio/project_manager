"""SQLAlchemy query counter — N+1 detection for dev and staging.

Usage:
    Call `register_query_counter(engine, environment)` once at engine creation.
    The ASGI middleware (`QueryCounterMiddleware`) resets the counter per request
    and calls `check_query_budget` at response time.

Production environments are fully excluded: no listener, no ContextVar overhead.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from sqlalchemy import event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

_PRODUCTION_ENVS: frozenset[str] = frozenset({"production", "prod"})

# Stores the running query count for the current async task/request context.
# None means the counter is not active (e.g. outside a request, or production).
_query_count: ContextVar[int | None] = ContextVar("_query_count", default=None)


def before_cursor_execute_listener(
    conn: Any,
    cursor: Any,
    statement: Any,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    """SQLAlchemy `before_cursor_execute` event handler.

    Increments the per-request counter only when it has been initialised
    (i.e. inside an active request context managed by QueryCounterMiddleware).
    """
    current = _query_count.get()
    if current is not None:
        _query_count.set(current + 1)


def register_query_counter(engine: AsyncEngine, environment: str) -> None:
    """Attach the `before_cursor_execute` listener to *engine*.

    No-op in production environments to eliminate any overhead.
    """
    if environment in _PRODUCTION_ENVS:
        return
    event.listen(engine.sync_engine, "before_cursor_execute", before_cursor_execute_listener)


def check_query_budget(endpoint: str, budget: int) -> None:
    """Emit a WARNING if the current request exceeded *budget* queries.

    Safe to call even when the counter is None (skips silently).
    """
    count = _query_count.get()
    if count is None:
        return
    if count > budget:
        logger.warning(
            "N+1 WARNING endpoint=%s queries=%d budget=%d — potential N+1 query pattern",
            endpoint,
            count,
            budget,
        )
