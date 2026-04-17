"""CORSPolicyMiddleware — strict CORS allowlist enforcement.

Wiring order in main.py:
  Must run AFTER CorrelationIDMiddleware and RequestLoggingMiddleware,
  and BEFORE RateLimitMiddleware and AuthMiddleware.

  Starlette runs middleware in reverse add_middleware order, so add this
  AFTER RequestLoggingMiddleware in main.py:

    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CORSPolicyMiddleware, ...)

# TODO: EP-12 phase 9 — wire in main.py
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
_ALLOWED_HEADERS = "Authorization, Content-Type, X-Correlation-ID, X-CSRF-Token"
_MAX_AGE = "600"


class CORSPolicyMiddleware(BaseHTTPMiddleware):
    """Strict CORS replacement for FastAPI's default CORSMiddleware.

    - Reflects the matching origin from the allowlist (never echoes '*').
    - Rejects '*' in allowed_origins when env == 'production'.
    - Preflight: responds 200 with limited allow_headers and max_age=600.
    - Non-CORS (no Origin header): passes through unchanged.
    - Disallowed origin: 403, no ACAO header.
    """

    def __init__(
        self,
        app: object,
        allowed_origins: list[str],
        env: str = "development",
    ) -> None:
        if env == "production" and "*" in allowed_origins:
            raise ValueError(
                "CORSPolicyMiddleware: wildcard '*' is not allowed in production. "
                "Set APP_CORS_ALLOWED_ORIGINS to explicit origins."
            )
        super().__init__(app)  # type: ignore[arg-type]
        self._allowed: frozenset[str] = frozenset(allowed_origins)
        self._env = env

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        origin = request.headers.get("origin")

        # Not a CORS request — pass through
        if not origin:
            return await call_next(request)

        origin_allowed = origin in self._allowed or "*" in self._allowed

        # Preflight
        if request.method == "OPTIONS":
            if not origin_allowed:
                return JSONResponse(
                    status_code=403,
                    content={"error": {"code": "CORS_ORIGIN_DISALLOWED", "message": "origin not allowed"}},
                )
            resp = Response(status_code=200)
            resp.headers["Access-Control-Allow-Origin"] = origin
            resp.headers["Access-Control-Allow-Methods"] = _ALLOWED_METHODS
            resp.headers["Access-Control-Allow-Headers"] = _ALLOWED_HEADERS
            resp.headers["Access-Control-Allow-Credentials"] = "true"
            resp.headers["Access-Control-Max-Age"] = _MAX_AGE
            return resp

        # Actual cross-origin request
        if not origin_allowed:
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "CORS_ORIGIN_DISALLOWED", "message": "origin not allowed"}},
            )

        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
        return response
