"""Rate limiting for /api/v1/auth/* — slowapi in-memory backend.

Single-process deployments only. Multi-replica migration to a shared store
(e.g. Redis) is tracked outside EP-00.

The key function prefers the leftmost `X-Forwarded-For` entry when present
(dev env sits behind Docker Compose networking) and falls back to the socket
peer address.

Controllers import `auth_limiter` and decorate routes at module load:

    @auth_limiter.limit(AUTH_LIMIT)
    async def my_route(request: Request, ...):

The limit is evaluated lazily per-request so `AUTH_SETTINGS.rate_limit_per_minute`
stays the source of truth.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


auth_limiter = Limiter(key_func=_client_ip)


def _auth_limit_value() -> str:
    from app.config.settings import get_settings

    return f"{get_settings().auth.rate_limit_per_minute}/minute"


AUTH_LIMIT = _auth_limit_value


def build_limiter(per_minute: int) -> Limiter:  # noqa: ARG001
    """Return the shared `auth_limiter`.

    `per_minute` is accepted for call-site clarity but ignored — the decorator
    evaluates `AUTH_LIMIT` lazily on every request via `get_settings()`, so
    changing the setting takes effect on the next request without rebuilding.
    """
    return auth_limiter
