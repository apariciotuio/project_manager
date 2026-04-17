"""SecurityHeadersMiddleware — CSP + HSTS + security response headers.

Wiring order in main.py:
  Must run AFTER CorrelationIDMiddleware and RequestLoggingMiddleware.
  Position: outermost-to-innermost → runs on every response regardless of
  what other middleware does.

  Recommended slot (add_middleware calls, last-in = outermost-run):
    app.add_middleware(CorrelationIDMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SecurityHeadersMiddleware, csp_overrides=settings.app.csp_overrides)
    app.add_middleware(CORSPolicyMiddleware, ...)

# TODO: EP-12 phase 9 — wire in main.py
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Base CSP directives. Intentionally strict:
# - no unsafe-inline for scripts
# - no unsafe-eval
# - object-src none (kills Flash/plugins)
# - frame-ancestors none (mirrors X-Frame-Options: DENY)
_DEFAULT_CSP: dict[str, str] = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self' 'unsafe-inline'",   # unsafe-inline for styles is acceptable; scripts are the risk
    "img-src": "'self' data:",
    "font-src": "'self'",
    "connect-src": "'self'",
    "object-src": "'none'",
    "frame-ancestors": "'none'",
    "base-uri": "'self'",
    "form-action": "'self'",
}


def _build_csp(overrides: dict[str, str]) -> str:
    directives = {**_DEFAULT_CSP, **overrides}
    return "; ".join(f"{k} {v}" for k, v in directives.items())


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Sets security-critical response headers on every response.

    Headers always set:
      - Content-Security-Policy (configurable via csp_overrides)
      - X-Frame-Options: DENY
      - X-Content-Type-Options: nosniff
      - Referrer-Policy: strict-origin-when-cross-origin

    Headers set only when request is HTTPS (X-Forwarded-Proto: https):
      - Strict-Transport-Security: max-age=31536000; includeSubDomains
    """

    def __init__(
        self,
        app: object,
        csp_overrides: dict[str, str] | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._csp = _build_csp(csp_overrides or {})

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        response.headers["Content-Security-Policy"] = self._csp
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if request.headers.get("x-forwarded-proto") == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
