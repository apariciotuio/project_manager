"""CSRF protection middleware — double-submit cookie pattern.

Safe methods (GET, HEAD, OPTIONS, TRACE) are exempt.
All state-changing methods (POST, PUT, PATCH, DELETE) must present a
`X-CSRF-Token` header whose value equals the `csrf_token` cookie value.
Comparison is constant-time via `hmac.compare_digest`.

Exempt paths (bootstrap & teardown endpoints, or no-CSRF-cookie-yet scenarios):
  - /api/v1/auth/google/callback — OAuth callback; no CSRF cookie yet, session bootstrapped here
  - /api/v1/auth/refresh — rotate access token; refresh cookie used, CSRF cookie refreshed in response
  - /api/v1/auth/logout — clear session; client has cookies but no CSRF header sent
  - /api/v1/csp-report — CSP violation reports from browsers; no user context
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "X-CSRF-Token"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


def _csrf_error() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "error": {"code": "CSRF_TOKEN_INVALID", "message": "CSRF token missing or invalid"}
        },
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.exempt_paths = exempt_paths or set()

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF check (exact match only)."""
        return path in self.exempt_paths

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        if self._is_exempt(request.url.path):
            return await call_next(request)

        cookie_token = request.cookies.get(CSRF_COOKIE, "")
        header_token = request.headers.get(CSRF_HEADER, "")

        if not cookie_token or not header_token:
            logger.warning(
                "CSRF check failed — missing token",
                extra={"path": request.url.path, "method": request.method},
            )
            return _csrf_error()

        if not hmac.compare_digest(cookie_token, header_token):
            logger.warning(
                "CSRF check failed — token mismatch",
                extra={"path": request.url.path, "method": request.method},
            )
            return _csrf_error()

        return await call_next(request)
