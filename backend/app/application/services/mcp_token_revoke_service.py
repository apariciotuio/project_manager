"""MCPTokenRevokeService — EP-18 Capability 1.

Idempotent revocation. Clears the cache on revoke so MCP server rejects
within the 5s SLO.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.mcp_token import MCPToken


class _MCPTokenRepo(Protocol):
    async def get_by_id(self, token_id: UUID, workspace_id: UUID) -> MCPToken | None: ...
    async def save(self, token: MCPToken) -> MCPToken: ...


class _Cache(Protocol):
    async def delete(self, key: str) -> None: ...


class MCPTokenNotFoundError(LookupError):
    pass


def _cache_key(lookup_key_hmac: bytes) -> str:
    return f"mcp:token:{lookup_key_hmac.hex()}"


class MCPTokenRevokeService:
    def __init__(
        self,
        token_repo: _MCPTokenRepo,
        cache: _Cache | None = None,
    ) -> None:
        self._token_repo = token_repo
        self._cache = cache

    async def revoke(self, token_id: UUID, workspace_id: UUID) -> None:
        """Revoke token. Idempotent — revoking an already-revoked token is a no-op."""
        token = await self._token_repo.get_by_id(token_id, workspace_id)
        if token is None:
            raise MCPTokenNotFoundError(f"token {token_id} not found in workspace {workspace_id}")

        if token.is_revoked:
            return  # idempotent

        token.revoke()
        await self._token_repo.save(token)

        # Invalidate cache so verification rejects within TTL window
        if self._cache is not None:
            await self._cache.delete(_cache_key(token.lookup_key_hmac))
