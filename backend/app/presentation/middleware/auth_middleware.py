"""Auth middleware — FastAPI dependency that validates the access_token cookie.

Reads `access_token` cookie → decodes JWT → returns a typed `CurrentUser`.
Errors are mapped to HTTP 401 with the standard error envelope and specific codes
(`MISSING_TOKEN`, `TOKEN_EXPIRED`, `INVALID_TOKEN`). WWW-Authenticate is NOT set
(we use cookies, not Bearer tokens).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException, Request, status

from app.infrastructure.adapters.jwt_adapter import (
    JwtAdapter,
    TokenExpiredError,
    TokenInvalidError,
)

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"


@dataclass(frozen=True)
class CurrentUser:
    id: UUID
    email: str
    workspace_id: UUID | None
    is_superadmin: bool


def _unauthorized(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": code, "message": message, "details": {}}},
    )


def build_current_user_dependency(
    jwt_adapter: JwtAdapter,
) -> Callable[[Request], Coroutine[object, object, CurrentUser]]:
    """Factory so routes can depend on `get_current_user` via a partial closure.

    FastAPI resolves dependencies by identity, so we wrap the adapter once at
    wiring time and return the callable.
    """

    async def get_current_user(request: Request) -> CurrentUser:
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)
        if not token:
            raise _unauthorized("MISSING_TOKEN", "access token cookie is required")
        try:
            claims = jwt_adapter.decode(token)
        except TokenExpiredError:
            raise _unauthorized("TOKEN_EXPIRED", "access token has expired") from None
        except TokenInvalidError as exc:
            logger.warning("invalid JWT: %s", type(exc).__name__)
            raise _unauthorized("INVALID_TOKEN", "access token is invalid") from None

        try:
            workspace_id = UUID(claims["workspace_id"]) if claims.get("workspace_id") else None
            return CurrentUser(
                id=UUID(claims["sub"]),
                email=claims["email"],
                workspace_id=workspace_id,
                is_superadmin=bool(claims.get("is_superadmin", False)),
            )
        except (KeyError, ValueError) as exc:
            logger.warning("malformed JWT claims: %s", exc)
            raise _unauthorized("INVALID_TOKEN", "access token claims are malformed") from exc

    return get_current_user
