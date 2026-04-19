"""MCPTokenIssueService — EP-18 Capability 1.

Issues new MCP tokens. Enforces:
  - workspace membership for target user
  - max 10 active tokens per user per workspace
  - max 90-day TTL
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from app.domain.models.mcp_token import MCPToken

_MAX_ACTIVE_TOKENS = 10
_MAX_TTL_DAYS = 90
_DEFAULT_TTL_DAYS = 30
_TOKEN_REGEX = re.compile(r"^mcp_[A-Za-z0-9_-]{43}$")


class _MembershipRepo(Protocol):
    async def get_membership_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> object | None: ...


class _MCPTokenRepo(Protocol):
    async def count_active_for_user(self, workspace_id: UUID, user_id: UUID) -> int: ...
    async def save(self, token: MCPToken) -> MCPToken: ...


class MCPTokenNotMemberError(ValueError):
    code = "USER_NOT_IN_WORKSPACE"


class MCPTokenLimitError(ValueError):
    code = "TOKEN_LIMIT_REACHED"


class MCPTokenTTLError(ValueError):
    code = "EXPIRES_IN_DAYS_TOO_LARGE"


@dataclass
class IssuedToken:
    id: UUID
    plaintext: str
    name: str
    expires_at: datetime


def generate_token_plaintext() -> str:
    """Generate a URL-safe base64url-encoded 32-byte secret with mcp_ prefix."""
    raw = secrets.token_urlsafe(32)  # 32 bytes → 43 base64url chars
    return f"mcp_{raw}"


def compute_lookup_key(plaintext: str, pepper: str) -> bytes:
    """HMAC-SHA256 of plaintext using pepper as key."""
    return hmac.new(pepper.encode(), plaintext.encode(), hashlib.sha256).digest()


def hash_token_argon2(plaintext: str) -> str:
    """Argon2id hash using argon2-cffi with tuned cost for < 50ms p95."""
    from argon2 import PasswordHasher
    from argon2.profiles import RFC_9106_LOW_MEMORY

    # Use low-memory profile tuned for < 50ms — not login-hardening profile.
    ph = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
    return ph.hash(plaintext)


class MCPTokenIssueService:
    def __init__(
        self,
        token_repo: _MCPTokenRepo,
        membership_repo: _MembershipRepo,
        pepper: str,
    ) -> None:
        self._token_repo = token_repo
        self._membership_repo = membership_repo
        self._pepper = pepper

    async def issue(
        self,
        *,
        workspace_id: UUID,
        target_user_id: UUID,
        name: str,
        expires_in_days: int = _DEFAULT_TTL_DAYS,
        scopes: list[str] | None = None,
        rotated_from: UUID | None = None,
    ) -> IssuedToken:
        if expires_in_days > _MAX_TTL_DAYS:
            raise MCPTokenTTLError(
                f"expires_in_days must be <= {_MAX_TTL_DAYS}; got {expires_in_days}"
            )

        membership = await self._membership_repo.get_membership_for_user(
            workspace_id, target_user_id
        )
        if membership is None:
            raise MCPTokenNotMemberError(
                f"user {target_user_id} is not a member of workspace {workspace_id}"
            )

        active_count = await self._token_repo.count_active_for_user(workspace_id, target_user_id)
        if active_count >= _MAX_ACTIVE_TOKENS:
            raise MCPTokenLimitError(
                f"user already holds {active_count} active tokens; max is {_MAX_ACTIVE_TOKENS}"
            )

        plaintext = generate_token_plaintext()
        assert _TOKEN_REGEX.match(plaintext), f"Generated token format invalid: {plaintext}"

        lookup_key = compute_lookup_key(plaintext, self._pepper)
        token_hash = hash_token_argon2(plaintext)
        expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        token = MCPToken.create(
            workspace_id=workspace_id,
            user_id=target_user_id,
            name=name,
            token_hash_argon2=token_hash,
            lookup_key_hmac=lookup_key,
            scopes=scopes or [],
            expires_at=expires_at,
            rotated_from=rotated_from,
        )
        saved = await self._token_repo.save(token)

        return IssuedToken(
            id=saved.id,
            plaintext=plaintext,
            name=saved.name,
            expires_at=saved.expires_at,
        )
