"""AuthService — OAuth orchestrator for EP-00.

Flow:
  initiate_oauth()  → generate state + PKCE, persist state row, return Google URL
  handle_callback() → consume state, exchange code, upsert user, resolve memberships,
                      emit JWT + refresh token, record audit events
  refresh_token()   → validate refresh session, issue a fresh JWT
  logout()          → revoke session, emit audit event
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.application.services.audit_service import AuditService
from app.application.services.membership_resolver_service import (
    MembershipResolverService,
    ResolverOutcome,
)
from app.application.services.superadmin_seed_service import SuperadminSeedService
from app.domain.models.session import Session
from app.domain.models.user import User
from app.domain.repositories.oauth_state_repository import IOAuthStateRepository
from app.domain.repositories.session_repository import ISessionRepository
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.adapters.google_oauth_adapter import (
    GoogleOAuthAdapter,
    OAuthExchangeError,
)
from app.infrastructure.adapters.jwt_adapter import (
    JwtAdapter,
    TokenExpiredError,
    TokenInvalidError,
)


class InvalidStateError(Exception):
    """OAuth state missing, already consumed, or expired."""


class NoWorkspaceAccessError(Exception):
    """User has zero active workspace memberships. Cannot log in."""


class SessionExpiredError(Exception):
    """Refresh token past its TTL."""


class SessionRevokedError(Exception):
    """Refresh token revoked (logout or admin action)."""


class UserSuspendedError(Exception):
    """User account is suspended or deleted."""


@dataclass(frozen=True)
class InitiateOAuthResult:
    authorization_url: str
    state: str  # for telemetry/tests; the browser only sees it as a query param


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime


@dataclass(frozen=True)
class CallbackResult:
    user: User
    outcome: ResolverOutcome
    tokens: TokenPair | None  # None when outcome.kind == 'no_access'
    return_to: str | None


def _generate_state() -> str:
    return secrets.token_urlsafe(32)


def _generate_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


class AuthService:
    def __init__(
        self,
        *,
        user_repo: IUserRepository,
        session_repo: ISessionRepository,
        oauth_state_repo: IOAuthStateRepository,
        google_oauth: GoogleOAuthAdapter,
        jwt_adapter: JwtAdapter,
        audit_service: AuditService,
        superadmin_seed: SuperadminSeedService,
        membership_resolver: MembershipResolverService,
        access_token_ttl_seconds: int,
        refresh_token_ttl_seconds: int,
        oauth_state_ttl_seconds: int = 300,
    ) -> None:
        self._users = user_repo
        self._sessions = session_repo
        self._oauth_states = oauth_state_repo
        self._google = google_oauth
        self._jwt = jwt_adapter
        self._audit = audit_service
        self._seed = superadmin_seed
        self._resolver = membership_resolver
        self._access_ttl = access_token_ttl_seconds
        self._refresh_ttl = refresh_token_ttl_seconds
        self._state_ttl = oauth_state_ttl_seconds

    async def initiate_oauth(
        self,
        *,
        return_to: str | None = None,
        last_chosen_workspace_id: UUID | None = None,
    ) -> InitiateOAuthResult:
        state = _generate_state()
        verifier, challenge = _generate_pkce()
        await self._oauth_states.create(
            state=state,
            verifier=verifier,
            ttl_seconds=self._state_ttl,
            return_to=return_to,
            last_chosen_workspace_id=last_chosen_workspace_id,
        )
        url = self._google.get_authorization_url(state=state, challenge=challenge)
        return InitiateOAuthResult(authorization_url=url, state=state)

    async def handle_callback(
        self,
        *,
        code: str,
        state: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> CallbackResult:
        consumed = await self._oauth_states.consume(state)
        if consumed is None:
            await self._audit.log_event(
                category="auth",
                action="login_invalid_state",
                context={
                    "outcome": "failure",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                },
            )
            raise InvalidStateError("oauth state missing, expired, or already consumed")

        try:
            claims = await self._google.exchange_code(code=code, verifier=consumed.verifier)
        except OAuthExchangeError:
            await self._audit.log_event(
                category="auth",
                action="login_failed_oauth_exchange",
                context={
                    "outcome": "failure",
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "state": state,
                },
            )
            raise

        existing = await self._users.get_by_google_sub(claims.sub)
        if existing:
            existing.update_from_google(name=claims.name, picture=claims.picture)
            existing.update_email(claims.email)  # re-validates; never bypass
            user = await self._users.upsert(existing)
        else:
            user = User.from_google_claims(
                sub=claims.sub,
                email=claims.email,
                name=claims.name,
                picture=claims.picture,
            )
            user = await self._users.upsert(user)
            await self._seed.on_user_created(user)

        outcome = await self._resolver.resolve(
            user_id=user.id,
            last_chosen_workspace_id=consumed.last_chosen_workspace_id,
        )

        if outcome.kind == "no_access":
            await self._audit.log_event(
                category="auth",
                action="login_blocked_no_workspace",
                actor_id=user.id,
                actor_display=user.email,
                context={"outcome": "failure", "ip_address": ip_address, "user_agent": user_agent},
            )
            raise NoWorkspaceAccessError(user.email)

        tokens = await self._issue_tokens(
            user=user,
            workspace_id=outcome.workspace_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._audit.log_event(
            category="auth",
            action="login_success",
            actor_id=user.id,
            actor_display=user.email,
            workspace_id=outcome.workspace_id,
            entity_type="user",
            entity_id=user.id,
            context={
                "outcome": "success",
                "ip_address": ip_address,
                "user_agent": user_agent,
                "routing": outcome.kind,
            },
        )

        return CallbackResult(
            user=user,
            outcome=outcome,
            tokens=tokens,
            return_to=consumed.return_to,
        )

    async def refresh_token(
        self,
        *,
        raw_refresh_token: str,
        workspace_id: UUID | None,
    ) -> TokenPair:
        if not raw_refresh_token:
            raise InvalidStateError("missing refresh token")
        token_hash = Session.hash_token(raw_refresh_token)
        session = await self._sessions.get_by_token_hash(token_hash)
        if session is None:
            raise InvalidStateError("unknown refresh token")
        if session.is_revoked():
            raise SessionRevokedError()
        if session.is_expired():
            raise SessionExpiredError()

        user = await self._users.get_by_id(session.user_id)
        if user is None:
            raise InvalidStateError("session user no longer exists")
        if user.status != "active":
            raise UserSuspendedError(f"user {user.id} status={user.status}")

        # Workspace IDOR guard: if workspace_id was supplied by the client,
        # verify the session user is an active member of it.
        effective_workspace_id: UUID | None
        if workspace_id is not None:
            memberships = await self._resolver._repo.get_active_by_user_id(user.id)
            member_ws_ids = {m.workspace_id for m in memberships}
            if workspace_id not in member_ws_ids:
                raise NoWorkspaceAccessError(
                    f"user {user.id} is not an active member of workspace {workspace_id}"
                )
            effective_workspace_id = workspace_id
        else:
            # Fall back to the workspace encoded in the session when it was created.
            # The session itself doesn't store workspace_id (it's in the JWT), so
            # we cannot validate here — caller is responsible for passing a valid id.
            effective_workspace_id = None

        access_token, access_exp = self._encode_access_token(
            user=user, workspace_id=effective_workspace_id
        )

        await self._audit.log_event(
            category="auth",
            action="token_refresh",
            actor_id=user.id,
            actor_display=user.email,
            workspace_id=effective_workspace_id,
        )

        return TokenPair(
            access_token=access_token,
            access_token_expires_at=access_exp,
            refresh_token=raw_refresh_token,  # refresh rotation is EP-10 scope
            refresh_token_expires_at=session.expires_at,
        )

    async def logout(self, *, raw_refresh_token: str, actor_id: UUID | None) -> None:
        if not raw_refresh_token:
            return
        token_hash = Session.hash_token(raw_refresh_token)
        session = await self._sessions.get_by_token_hash(token_hash)
        if session is None:
            return
        await self._sessions.revoke(session.id)
        await self._audit.log_event(
            category="auth",
            action="logout",
            actor_id=actor_id or session.user_id,
        )

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            return self._jwt.decode(token)
        except (TokenExpiredError, TokenInvalidError):
            raise

    async def _issue_tokens(
        self,
        *,
        user: User,
        workspace_id: UUID | None,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        access_token, access_exp = self._encode_access_token(user=user, workspace_id=workspace_id)
        raw_refresh = _generate_refresh_token()
        session = Session.create(
            user_id=user.id,
            raw_token=raw_refresh,
            ttl_seconds=self._refresh_ttl,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._sessions.create(session)
        return TokenPair(
            access_token=access_token,
            access_token_expires_at=access_exp,
            refresh_token=raw_refresh,
            refresh_token_expires_at=session.expires_at,
        )

    def _encode_access_token(
        self, *, user: User, workspace_id: UUID | None
    ) -> tuple[str, datetime]:
        now = datetime.now(UTC)
        exp = now + timedelta(seconds=self._access_ttl)
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "workspace_id": str(workspace_id) if workspace_id else None,
            "is_superadmin": user.is_superadmin,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return self._jwt.encode(payload), exp
