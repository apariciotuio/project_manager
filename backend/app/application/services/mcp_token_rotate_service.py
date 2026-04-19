"""MCPTokenRotateService — EP-18 Capability 1.

Revokes old token and issues a new one with same name + workspace.
Records rotated_from on the new token.
"""
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.application.services.mcp_token_issue_service import IssuedToken, MCPTokenIssueService
from app.application.services.mcp_token_revoke_service import (
    MCPTokenNotFoundError,
    MCPTokenRevokeService,
)
from app.domain.models.mcp_token import MCPToken

_DEFAULT_ROTATE_TTL_DAYS = 30


class _MCPTokenRepo(Protocol):
    async def get_by_id(self, token_id: UUID, workspace_id: UUID) -> MCPToken | None: ...


class MCPTokenRotateService:
    def __init__(
        self,
        token_repo: _MCPTokenRepo,
        revoke_service: MCPTokenRevokeService,
        issue_service: MCPTokenIssueService,
    ) -> None:
        self._token_repo = token_repo
        self._revoke_service = revoke_service
        self._issue_service = issue_service

    async def rotate(
        self,
        token_id: UUID,
        workspace_id: UUID,
        expires_in_days: int = _DEFAULT_ROTATE_TTL_DAYS,
    ) -> IssuedToken:
        """Revoke old token and issue a new one. Returns the new IssuedToken."""
        token = await self._token_repo.get_by_id(token_id, workspace_id)
        if token is None:
            raise MCPTokenNotFoundError(
                f"token {token_id} not found in workspace {workspace_id}"
            )

        await self._revoke_service.revoke(token_id, workspace_id)

        new_token = await self._issue_service.issue(
            workspace_id=workspace_id,
            target_user_id=token.user_id,
            name=token.name,
            expires_in_days=expires_in_days,
            scopes=token.scopes,
            rotated_from=token_id,
        )
        return new_token
