"""IMCPTokenRepository — EP-18 Capability 1."""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.mcp_token import MCPToken


class IMCPTokenRepository(Protocol):
    async def get_by_lookup_key(self, lookup_key_hmac: bytes) -> MCPToken | None: ...

    async def get_by_id(self, token_id: UUID, workspace_id: UUID) -> MCPToken | None: ...

    async def save(self, token: MCPToken) -> MCPToken: ...

    async def list_for_user(
        self,
        workspace_id: UUID,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> list[MCPToken]: ...

    async def count_active_for_user(self, workspace_id: UUID, user_id: UUID) -> int: ...
