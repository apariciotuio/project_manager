"""BodySizeLimitMiddleware — rejects oversized request bodies.

Wiring order in main.py:
  Should run AFTER CorrelationIDMiddleware and RequestLoggingMiddleware,
  and BEFORE AuthMiddleware so oversized anonymous floods are cheap to reject.

  app.add_middleware(CorrelationIDMiddleware)
  app.add_middleware(RequestLoggingMiddleware)
  app.add_middleware(BodySizeLimitMiddleware,
                     max_body_bytes=settings.app.max_body_bytes,
                     large_body_prefixes=["/api/v1/attachments"],
                     large_body_limit=10 * 1024 * 1024)
  app.add_middleware(CORSPolicyMiddleware, ...)
  app.add_middleware(SecurityHeadersMiddleware, ...)

# TODO: EP-12 phase 9 — wire in main.py
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_1_MiB = 1024 * 1024
_DEFAULT_MAX_BODY_BYTES = _1_MiB
_DEFAULT_LARGE_LIMIT = 10 * _1_MiB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose Content-Length exceeds the configured limit.

    Two-tier limits:
    - Default: max_body_bytes (default 1 MiB) for all paths.
    - Large: large_body_limit (default 10 MiB) for paths under large_body_prefixes.

    Enforcement is header-based (Content-Length). Requests without Content-Length
    are passed through — stream-based enforcement requires reading the body which
    defeats the purpose of early rejection.
    """

    def __init__(
        self,
        app: object,
        max_body_bytes: int = _DEFAULT_MAX_BODY_BYTES,
        large_body_prefixes: list[str] | None = None,
        large_body_limit: int = _DEFAULT_LARGE_LIMIT,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._max_body_bytes = max_body_bytes
        self._large_prefixes = tuple(large_body_prefixes or [])
        self._large_body_limit = large_body_limit

    def _limit_for(self, path: str) -> int:
        for prefix in self._large_prefixes:
            if path.startswith(prefix):
                return self._large_body_limit
        return self._max_body_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        content_length_header = request.headers.get("content-length")
        if content_length_header is not None:
            try:
                content_length = int(content_length_header)
            except ValueError:
                content_length = 0

            limit = self._limit_for(request.url.path)
            if content_length > limit:
                logger.warning(
                    "request body too large: %d > %d on %s %s",
                    content_length,
                    limit,
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "BODY_TOO_LARGE",
                            "message": f"request body exceeds {limit} bytes",
                        }
                    },
                )

        return await call_next(request)
