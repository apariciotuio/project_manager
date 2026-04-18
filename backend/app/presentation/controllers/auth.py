"""EP-00 auth controller — 5 routes. All business logic lives in AuthService."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse

from app.infrastructure.adapters.jwt_adapter import (
    JwtAdapter,
    TokenExpiredError,
    TokenInvalidError,
)
from app.presentation.dependencies import get_jwt_adapter

from app.application.services.auth_service import (
    AuthService,
    InvalidStateError,
    NoWorkspaceAccessError,
    SessionExpiredError,
    SessionRevokedError,
    UserSuspendedError,
)
from app.infrastructure.adapters.google_oauth_adapter import OAuthExchangeError
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_repository_impl import (
    WorkspaceRepositoryImpl,
)
from app.presentation.dependencies import (
    get_auth_service,
    get_current_user,
    get_user_repo,
    get_workspace_repo,
)
from app.presentation.middleware.auth_middleware import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    CurrentUser,
)
from app.presentation.rate_limit import AUTH_LIMIT, auth_limiter

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_PATH = "/api/v1/auth/refresh"


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message, "details": {}}}


def _safe_return_to(value: str | None) -> str | None:
    """Validate that return_to is a safe relative path — blocks open redirect.

    Accepts only paths that:
    - start with "/"
    - do NOT start with "//" (protocol-relative)
    - do NOT start with "/\\" (IE-style protocol-relative)
    - contain no scheme ("://")
    - contain no "@" (userinfo confusion)
    """
    if value is None:
        return None
    if not value.startswith("/"):
        return None
    if value.startswith("//") or value.startswith("/\\"):
        return None
    if "://" in value:
        return None
    if "@" in value:
        return None
    return value


def _set_access_cookie(
    response: Response, token: str, max_age_seconds: int, *, secure: bool
) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _set_refresh_cookie(
    response: Response, token: str, max_age_seconds: int, *, secure: bool
) -> None:
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


def _set_csrf_cookie(response: Response, max_age_seconds: int, *, secure: bool) -> None:
    """Emit a non-HttpOnly CSRF token cookie (double-submit cookie pattern).

    JS reads this value and sends it back as X-CSRF-Token on state-changing requests.
    CSRFMiddleware compares header == cookie via hmac.compare_digest.
    """
    response.set_cookie(
        key="csrf_token",
        value=secrets.token_urlsafe(32),
        max_age=max_age_seconds,
        httponly=False,  # JS must read this to inject the header
        secure=secure,
        samesite="strict",
        path="/",
    )


def _clear_cookies(response: Response, *, secure: bool = False) -> None:
    response.delete_cookie(
        ACCESS_TOKEN_COOKIE,
        path="/",
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.delete_cookie(
        REFRESH_TOKEN_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite="lax",
    )


@router.get("/google")
@auth_limiter.limit(AUTH_LIMIT)
async def initiate_oauth(
    request: Request,
    return_to: str | None = None,
    last_chosen_workspace_id: UUID | None = None,
    auth: AuthService = Depends(get_auth_service),
) -> RedirectResponse:
    safe_return_to = _safe_return_to(return_to)
    result = await auth.initiate_oauth(
        return_to=safe_return_to,
        last_chosen_workspace_id=last_chosen_workspace_id,
    )
    return RedirectResponse(url=result.authorization_url, status_code=302)


@router.get("/google/callback")
@auth_limiter.limit(AUTH_LIMIT)
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    auth: AuthService = Depends(get_auth_service),
    workspaces: WorkspaceRepositoryImpl = Depends(get_workspace_repo),
) -> RedirectResponse:
    # Google sends ?error=access_denied when the user cancels the consent screen.
    if error:
        return RedirectResponse(url="/login?error=cancelled", status_code=302)
    if not state:
        return RedirectResponse(url="/login?error=invalid_state", status_code=302)
    if not code:
        return RedirectResponse(url="/login?error=oauth_failed", status_code=302)

    secure_cookies = request.url.scheme == "https"
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    try:
        result = await auth.handle_callback(
            code=code,
            state=state,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except InvalidStateError:
        return RedirectResponse(url="/login?error=invalid_state", status_code=302)
    except OAuthExchangeError:
        return RedirectResponse(url="/login?error=provider_error", status_code=302)
    except NoWorkspaceAccessError:
        return RedirectResponse(url="/login?error=no_workspace", status_code=302)

    tokens = result.tokens
    assert tokens is not None  # no_access would have raised above

    # return_to was stored with the state row; never read from callback query params
    safe_return_to = _safe_return_to(result.return_to)

    if result.outcome.kind == "picker":
        location = "/workspace/select"
    else:
        ws = await workspaces.get_by_id(result.outcome.workspace_id)  # type: ignore[arg-type]
        slug = ws.slug if ws else "select"
        if safe_return_to:
            location = f"/workspace/{slug}?returnTo={quote(safe_return_to)}"
        else:
            location = f"/workspace/{slug}"

    response = RedirectResponse(url=location, status_code=302)
    access_ttl = max(1, int((tokens.access_token_expires_at - datetime.now(timezone.utc)).total_seconds()))
    refresh_ttl = max(
        1,
        int((tokens.refresh_token_expires_at - datetime.now(timezone.utc)).total_seconds()),
    )
    _set_access_cookie(
        response, tokens.access_token, access_ttl, secure=secure_cookies
    )
    _set_refresh_cookie(
        response, tokens.refresh_token, refresh_ttl, secure=secure_cookies
    )
    _set_csrf_cookie(response, access_ttl, secure=secure_cookies)
    return response


@router.post("/refresh")
@auth_limiter.limit(AUTH_LIMIT)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    workspace_slug: str | None = None,
    auth: AuthService = Depends(get_auth_service),
    workspaces: WorkspaceRepositoryImpl = Depends(get_workspace_repo),
) -> dict:
    secure_cookies = request.url.scheme == "https"
    if not refresh_token:
        _clear_cookies(response, secure=secure_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("MISSING_TOKEN", "refresh token cookie is required"),
        )

    workspace_id = None
    if workspace_slug:
        ws = await workspaces.get_by_slug(workspace_slug)
        workspace_id = ws.id if ws else None

    try:
        pair = await auth.refresh_token(
            raw_refresh_token=refresh_token, workspace_id=workspace_id
        )
    except SessionExpiredError:
        _clear_cookies(response, secure=secure_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("SESSION_EXPIRED", "refresh token has expired"),
        ) from None
    except SessionRevokedError:
        _clear_cookies(response, secure=secure_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("SESSION_REVOKED", "refresh token was revoked"),
        ) from None
    except (InvalidStateError, UserSuspendedError):
        _clear_cookies(response, secure=secure_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("INVALID_TOKEN", "refresh token is invalid or user suspended"),
        ) from None
    except NoWorkspaceAccessError:
        _clear_cookies(response, secure=secure_cookies)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("NO_WORKSPACE_ACCESS", "user is not a member of the requested workspace"),
        ) from None

    access_ttl = max(
        1,
        int((pair.access_token_expires_at - datetime.now(timezone.utc)).total_seconds()),
    )
    _set_access_cookie(
        response, pair.access_token, access_ttl, secure=secure_cookies
    )
    _set_csrf_cookie(response, access_ttl, secure=secure_cookies)
    return {
        "data": {
            "access_token_expires_at": pair.access_token_expires_at.isoformat(),
        }
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@auth_limiter.limit(AUTH_LIMIT)
async def logout(
    request: Request,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    access_token: str | None = Cookie(default=None, alias=ACCESS_TOKEN_COOKIE),
    auth: AuthService = Depends(get_auth_service),
    jwt_adapter: JwtAdapter = Depends(get_jwt_adapter),
) -> Response:
    """Logout never 401s: even with expired or missing tokens we still clear cookies."""
    actor_id: UUID | None = None
    if access_token:
        try:
            claims = jwt_adapter.decode(access_token)
            actor_id = UUID(claims["sub"])
        except (TokenExpiredError, TokenInvalidError, KeyError, ValueError):
            pass  # best-effort: logout must always succeed

    if refresh_token:
        await auth.logout(raw_refresh_token=refresh_token, actor_id=actor_id)

    secure_cookies = request.url.scheme == "https"
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", httponly=True, secure=secure_cookies, samesite="lax")
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, secure=secure_cookies, samesite="lax")
    return response


@router.get("/me")
@auth_limiter.limit(AUTH_LIMIT)
async def me(
    request: Request,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    users: UserRepositoryImpl = Depends(get_user_repo),
    workspaces: WorkspaceRepositoryImpl = Depends(get_workspace_repo),
) -> dict:
    record = await users.get_by_id(user.id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_error("INVALID_TOKEN", "user no longer exists"),
        )
    # Bootstrap CSRF cookie for sessions that predate CSRF middleware rollout
    # or that lost the cookie. Cheap idempotent side-effect on any /me call.
    if not request.cookies.get("csrf_token"):
        secure_cookies = request.url.scheme == "https"
        _set_csrf_cookie(response, max_age_seconds=60 * 60 * 24, secure=secure_cookies)
    workspace_slug: str | None = None
    if user.workspace_id:
        ws = await workspaces.get_by_id(user.workspace_id)
        workspace_slug = ws.slug if ws else None
    return {
        "data": {
            "id": str(record.id),
            "email": record.email,
            "full_name": record.full_name,
            "avatar_url": record.avatar_url,
            "workspace_id": str(user.workspace_id) if user.workspace_id else None,
            "workspace_slug": workspace_slug,
            "is_superadmin": record.is_superadmin,
        }
    }
