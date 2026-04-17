"""RequestLoggingMiddleware — structured log line per request.

Wiring order in main.py:
  Must run AFTER CorrelationIDMiddleware (needs the ContextVar already set)
  and BEFORE all other middleware so it captures the full request lifecycle.

  app.add_middleware(RequestLoggingMiddleware)   # added 2nd — runs 2nd outermost
  app.add_middleware(CorrelationIDMiddleware)    # added 1st — runs outermost

# TODO: EP-12 phase 9 — wire in main.py
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config.logging import correlation_id_var

logger = logging.getLogger(__name__)

_SENSITIVE_HEADERS = frozenset(
    {"authorization", "cookie", "set-cookie", "x-api-key", "x-auth-token"}
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Emits one JSON-compatible structured log line per HTTP request.

    Fields: method, path, status_code, duration_ms, correlation_id, user_id.
    Never logs Authorization headers, cookies, or request bodies.
    4xx → INFO, 5xx → ERROR, everything else → INFO.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        status = response.status_code
        level = logging.ERROR if status >= 500 else logging.INFO

        user_id: str | None = None
        if hasattr(request.state, "user_id"):
            user_id = str(request.state.user_id)

        logger.log(
            level,
            "%s %s %d",
            request.method,
            request.url.path,
            status,
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status,
                "duration_ms": round(duration_ms, 3),
                "correlation_id": correlation_id_var.get(""),
                "user_id": user_id,
            },
        )

        return response
