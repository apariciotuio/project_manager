"""ASGI middleware for per-request query budget enforcement.

Wraps each request in a fresh ContextVar token so the SQLAlchemy
`before_cursor_execute` listener counts queries in isolation.
Calls `check_query_budget` at response time (dev/staging only).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.db.query_counter import (
    _PRODUCTION_ENVS,
    _query_count,
    check_query_budget,
)

_DEFAULT_BUDGET = 20


class QueryCounterMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: Callable[..., Awaitable[Response]],
        *,
        budget: int = _DEFAULT_BUDGET,
        environment: str = "development",
    ) -> None:
        super().__init__(app)
        self._budget = budget
        self._active = environment not in _PRODUCTION_ENVS

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._active:
            return await call_next(request)

        token = _query_count.set(0)
        try:
            response = await call_next(request)
        finally:
            endpoint = request.url.path
            check_query_budget(endpoint=endpoint, budget=self._budget)
            _query_count.reset(token)

        return response
