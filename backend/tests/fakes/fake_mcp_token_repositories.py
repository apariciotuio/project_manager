"""In-memory fakes for MCP token domain — EP-18 unit tests."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.domain.models.mcp_token import MCPToken


class FakeMCPTokenRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, MCPToken] = {}

    async def get_by_lookup_key(self, lookup_key_hmac: bytes) -> MCPToken | None:
        return next(
            (t for t in self._by_id.values() if t.lookup_key_hmac == lookup_key_hmac),
            None,
        )

    async def get_by_id(self, token_id: UUID, workspace_id: UUID) -> MCPToken | None:
        t = self._by_id.get(token_id)
        if t is None or t.workspace_id != workspace_id:
            return None
        return t

    async def save(self, token: MCPToken) -> MCPToken:
        self._by_id[token.id] = token
        return token

    async def list_for_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> list[MCPToken]:
        return [
            t
            for t in self._by_id.values()
            if t.workspace_id == workspace_id
            and t.user_id == user_id
            and (include_revoked or not t.is_revoked)
        ]

    async def count_active_for_user(self, workspace_id: UUID, user_id: UUID) -> int:
        now = datetime.now(UTC)
        return sum(
            1
            for t in self._by_id.values()
            if t.workspace_id == workspace_id
            and t.user_id == user_id
            and t.revoked_at is None
            and t.expires_at > now
        )


class FakeMembershipRepo:
    """Minimal fake for membership check in MCPTokenIssueService."""

    def __init__(self, members: set[tuple[UUID, UUID]] | None = None) -> None:
        # Set of (workspace_id, user_id) tuples for active members
        self._members: set[tuple[UUID, UUID]] = members or set()

    def add_member(self, workspace_id: UUID, user_id: UUID) -> None:
        self._members.add((workspace_id, user_id))

    async def get_membership_for_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> object | None:
        if (workspace_id, user_id) in self._members:
            return object()
        return None


class FakeCache:
    """Simple in-memory cache fake."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key: str) -> object | None:
        return self._store.get(key)

    async def set(self, key: str, value: object, ttl_seconds: int = 5) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
