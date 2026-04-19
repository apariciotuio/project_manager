"""EP-18 — Admin MCP tokens controller.

Routes:
  POST   /api/v1/admin/mcp-tokens               issue
  GET    /api/v1/admin/mcp-tokens?user_id=?     list
  DELETE /api/v1/admin/mcp-tokens/{id}          revoke
  POST   /api/v1/admin/mcp-tokens/{id}/rotate   rotate
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.mcp_token_issue_service import (
    MCPTokenIssueService,
    MCPTokenLimitError,
    MCPTokenNotMemberError,
    MCPTokenTTLError,
)
from app.application.services.mcp_token_revoke_service import (
    MCPTokenNotFoundError,
    MCPTokenRevokeService,
)
from app.application.services.mcp_token_rotate_service import MCPTokenRotateService
from app.domain.repositories.mcp_token_repository import IMCPTokenRepository
from app.infrastructure.persistence.mcp_token_repository_impl import MCPTokenRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.presentation.capabilities import build_require_capabilities
from app.presentation.dependencies import get_capability_repo, get_current_user, get_db_session
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/mcp-tokens", tags=["admin-mcp-tokens"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _token_payload(t: Any) -> dict[str, Any]:
    return {
        "id": str(t.id),
        "workspace_id": str(t.workspace_id),
        "user_id": str(t.user_id),
        "name": t.name,
        "scopes": t.scopes,
        "created_at": t.created_at.isoformat(),
        "expires_at": t.expires_at.isoformat(),
        "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
        "revoked_at": t.revoked_at.isoformat() if t.revoked_at else None,
        "rotated_from": str(t.rotated_from) if t.rotated_from else None,
    }


def _get_token_repo(session: AsyncSession = Depends(get_db_session)) -> MCPTokenRepositoryImpl:
    return MCPTokenRepositoryImpl(session)


def _get_membership_repo(
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMembershipRepositoryImpl:
    return WorkspaceMembershipRepositoryImpl(session)


def _get_pepper() -> str:
    from app.config.settings import get_settings  # deferred — avoids lru_cache trap

    return get_settings().mcp.token_pepper


class IssueRequest(BaseModel):
    user_id: UUID
    name: str = Field(..., min_length=1, max_length=200)
    expires_in_days: int = Field(default=30, ge=1, le=90)
    scopes: list[str] = []


class RotateRequest(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=90)


_mcp_issue_cap_dep = build_require_capabilities("mcp:issue")


async def _require_mcp_issue(
    current_user: CurrentUser = Depends(get_current_user),
    repo: object = Depends(get_capability_repo),
) -> CurrentUser:
    """Proper FastAPI dep: injects CurrentUser via get_current_user then capability-checks."""
    return await _mcp_issue_cap_dep(current_user, repo)  # type: ignore[arg-type]


@router.post(
    "",
    status_code=http_status.HTTP_201_CREATED,
    dependencies=[Depends(_require_mcp_issue)],
)
async def issue_token(
    body: IssueRequest,
    current_user: CurrentUser = Depends(get_current_user),
    token_repo: MCPTokenRepositoryImpl = Depends(_get_token_repo),
    membership_repo: WorkspaceMembershipRepositoryImpl = Depends(_get_membership_repo),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None

    pepper = _get_pepper()

    # Wrap membership_repo to expose get_membership_for_user
    class _MembershipAdapter:
        def __init__(self, repo: WorkspaceMembershipRepositoryImpl) -> None:
            self._repo = repo

        async def get_membership_for_user(
            self, workspace_id: UUID, user_id: UUID
        ) -> object | None:
            return await self._repo.get_for_user_and_workspace(user_id, workspace_id)

    svc = MCPTokenIssueService(
        token_repo=token_repo,
        membership_repo=_MembershipAdapter(membership_repo),
        pepper=pepper,
    )

    try:
        issued = await svc.issue(
            workspace_id=current_user.workspace_id,
            target_user_id=body.user_id,
            name=body.name,
            expires_in_days=body.expires_in_days,
            scopes=body.scopes,
        )
    except MCPTokenNotMemberError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "USER_NOT_IN_WORKSPACE", "message": str(exc), "details": {}}},
        ) from exc
    except MCPTokenLimitError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "TOKEN_LIMIT_REACHED", "message": str(exc), "details": {}}},
        ) from exc
    except MCPTokenTTLError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "EXPIRES_IN_DAYS_TOO_LARGE", "message": str(exc), "details": {}}},
        ) from exc

    return _ok(
        {
            "id": str(issued.id),
            "plaintext": issued.plaintext,  # returned ONCE
            "name": issued.name,
            "expires_at": issued.expires_at.isoformat(),
        },
        message="token issued",
    )


@router.get("", dependencies=[Depends(_require_mcp_issue)])
async def list_tokens(
    user_id: UUID,
    include_revoked: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
    token_repo: MCPTokenRepositoryImpl = Depends(_get_token_repo),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None

    tokens = await token_repo.list_for_user(
        workspace_id=current_user.workspace_id,
        user_id=user_id,
        include_revoked=include_revoked,
    )
    return _ok([_token_payload(t) for t in tokens])


@router.delete("/{token_id}", status_code=http_status.HTTP_204_NO_CONTENT, dependencies=[Depends(_require_mcp_issue)])
async def revoke_token(
    token_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    token_repo: MCPTokenRepositoryImpl = Depends(_get_token_repo),
) -> None:
    assert current_user.workspace_id is not None

    svc = MCPTokenRevokeService(token_repo=token_repo)
    try:
        await svc.revoke(token_id, current_user.workspace_id)
    except MCPTokenNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TOKEN_NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc


@router.post("/{token_id}/rotate", status_code=http_status.HTTP_201_CREATED, dependencies=[Depends(_require_mcp_issue)])
async def rotate_token(
    token_id: UUID,
    body: RotateRequest = RotateRequest(),
    current_user: CurrentUser = Depends(get_current_user),
    token_repo: MCPTokenRepositoryImpl = Depends(_get_token_repo),
    membership_repo: WorkspaceMembershipRepositoryImpl = Depends(_get_membership_repo),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None

    pepper = _get_pepper()

    class _MembershipAdapter:
        def __init__(self, repo: WorkspaceMembershipRepositoryImpl) -> None:
            self._repo = repo

        async def get_membership_for_user(
            self, workspace_id: UUID, user_id: UUID
        ) -> object | None:
            return await self._repo.get_for_user_and_workspace(user_id, workspace_id)

    issue_svc = MCPTokenIssueService(
        token_repo=token_repo,
        membership_repo=_MembershipAdapter(membership_repo),
        pepper=pepper,
    )
    revoke_svc = MCPTokenRevokeService(token_repo=token_repo)
    rotate_svc = MCPTokenRotateService(
        token_repo=token_repo,
        revoke_service=revoke_svc,
        issue_service=issue_svc,
    )

    try:
        new_issued = await rotate_svc.rotate(
            token_id,
            current_user.workspace_id,
            expires_in_days=body.expires_in_days,
        )
    except MCPTokenNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "TOKEN_NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc

    return _ok(
        {
            "id": str(new_issued.id),
            "plaintext": new_issued.plaintext,
            "name": new_issued.name,
            "expires_at": new_issued.expires_at.isoformat(),
        },
        message="token rotated",
    )
