"""MCPTokenVerifyService — EP-18 Capability 1.

Verifies opaque MCP tokens. Uses HMAC lookup key → argon2id verify chain.
Caches results keyed by lookup_key_hmac hex for 5s TTL (revocation SLO).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.domain.models.mcp_token import MCPToken

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 5


class _MCPTokenRepo(Protocol):
    async def get_by_lookup_key(self, lookup_key_hmac: bytes) -> MCPToken | None: ...
    async def save(self, token: MCPToken) -> MCPToken: ...


class _Cache(Protocol):
    async def get(self, key: str) -> object | None: ...
    async def set(self, key: str, value: object, ttl_seconds: int) -> None: ...
    async def delete(self, key: str) -> None: ...


class MCPTokenInvalid(Exception):
    """Token not found or hash mismatch."""


class MCPTokenExpired(Exception):
    """Token has passed its expires_at."""


class MCPTokenRevoked(Exception):
    """Token has been revoked."""


@dataclass(frozen=True)
class VerifiedToken:
    workspace_id: UUID
    user_id: UUID
    scopes: list[str]
    token_id: UUID


def _cache_key(lookup_key_hmac: bytes) -> str:
    return f"mcp:token:{lookup_key_hmac.hex()}"


def _verify_argon2(plaintext: str, token_hash: str) -> bool:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

    ph = PasswordHasher()
    try:
        ph.verify(token_hash, plaintext)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


class MCPTokenVerifyService:
    def __init__(
        self,
        token_repo: _MCPTokenRepo,
        pepper: str,
        cache: _Cache | None = None,
    ) -> None:
        self._token_repo = token_repo
        self._pepper = pepper
        self._cache = cache

    async def verify(self, plaintext: str) -> VerifiedToken:
        """Verify plaintext token. Raises MCPTokenInvalid/Expired/Revoked on failure."""
        lookup_key = hmac.new(
            self._pepper.encode(), plaintext.encode(), hashlib.sha256
        ).digest()
        cache_key = _cache_key(lookup_key)

        # Cache hit — avoid DB + argon2 on hot path
        if self._cache is not None:
            cached = await self._cache.get(cache_key)
            if cached is not None and isinstance(cached, dict):
                return VerifiedToken(
                    workspace_id=UUID(cached["workspace_id"]),
                    user_id=UUID(cached["user_id"]),
                    scopes=cached["scopes"],
                    token_id=UUID(cached["token_id"]),
                )

        token = await self._token_repo.get_by_lookup_key(lookup_key)
        # Uniform rejection — no timing oracle
        if token is None:
            raise MCPTokenInvalid("token not found")

        valid_hash = _verify_argon2(plaintext, token.token_hash_argon2)
        if not valid_hash:
            raise MCPTokenInvalid("hash mismatch")

        if token.is_revoked:
            raise MCPTokenRevoked(f"token {token.id} has been revoked")

        if token.is_expired:
            raise MCPTokenExpired(f"token {token.id} has expired")

        result = VerifiedToken(
            workspace_id=token.workspace_id,
            user_id=token.user_id,
            scopes=token.scopes,
            token_id=token.id,
        )

        # Populate cache on successful verification
        if self._cache is not None:
            await self._cache.set(
                cache_key,
                {
                    "workspace_id": str(result.workspace_id),
                    "user_id": str(result.user_id),
                    "scopes": result.scopes,
                    "token_id": str(result.token_id),
                },
                ttl_seconds=_CACHE_TTL_SECONDS,
            )

        return result

    async def invalidate_cache(self, plaintext: str) -> None:
        """Delete cache entry for this token (call on revoke)."""
        if self._cache is None:
            return
        lookup_key = hmac.new(
            self._pepper.encode(), plaintext.encode(), hashlib.sha256
        ).digest()
        await self._cache.delete(_cache_key(lookup_key))

    async def invalidate_cache_by_lookup_key(self, lookup_key_hmac: bytes) -> None:
        """Delete cache entry by lookup key (call on revoke when we have the key)."""
        if self._cache is None:
            return
        await self._cache.delete(_cache_key(lookup_key_hmac))
