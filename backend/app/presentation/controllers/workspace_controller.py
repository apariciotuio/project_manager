"""Workspace picker endpoints — EP-00.

Routes:
  GET  /api/v1/workspaces/mine    — list workspaces the current user belongs to
  POST /api/v1/workspaces/select  — set active workspace (updates session)
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.models.orm import (
    SessionORM,
    UserORM,
    WorkspaceMembershipORM,
    WorkspaceORM,
)
from app.presentation.dependencies import get_current_user
from app.presentation.middleware.auth_middleware import CurrentUser

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class SelectWorkspaceRequest(BaseModel):
    workspace_id: str


@router.get("/mine")
async def list_my_workspaces(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return workspaces the current user is a member of."""
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                WorkspaceORM.id,
                WorkspaceORM.name,
                WorkspaceORM.slug,
                WorkspaceMembershipORM.role,
            )
            .join(
                WorkspaceMembershipORM,
                WorkspaceMembershipORM.workspace_id == WorkspaceORM.id,
            )
            .where(
                WorkspaceMembershipORM.user_id == current_user.id,
                WorkspaceMembershipORM.state == "active",
                WorkspaceORM.status == "active",
            )
        )
        rows = (await session.execute(stmt)).all()

    return {
        "data": [
            {
                "id": str(row.id),
                "name": row.name,
                "slug": row.slug,
                "role": row.role,
            }
            for row in rows
        ],
        "message": "ok",
    }


@router.get("/members")
async def list_workspace_members(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Return active members of the current user's workspace.

    Used by frontend pickers (assign owner, add team member) so users
    don't have to paste UUIDs.
    """
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    factory = get_session_factory()
    async with factory() as session:
        stmt = (
            select(
                UserORM.id,
                UserORM.email,
                UserORM.full_name,
                UserORM.avatar_url,
                WorkspaceMembershipORM.role,
            )
            .join(
                WorkspaceMembershipORM,
                WorkspaceMembershipORM.user_id == UserORM.id,
            )
            .where(
                WorkspaceMembershipORM.workspace_id == current_user.workspace_id,
                WorkspaceMembershipORM.state == "active",
            )
            .order_by(UserORM.full_name.asc())
        )
        rows = (await session.execute(stmt)).all()

    return {
        "data": [
            {
                "id": str(row.id),
                "email": row.email,
                "full_name": row.full_name,
                "avatar_url": row.avatar_url,
                "role": row.role,
            }
            for row in rows
        ],
        "message": "ok",
    }


@router.post("/select")
async def select_workspace(
    body: SelectWorkspaceRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Set the active workspace for the current user's session.

    This updates the user's last_chosen_workspace_id so the next JWT
    refresh includes the workspace_id claim.
    """
    workspace_id = UUID(body.workspace_id)

    factory = get_session_factory()
    async with factory() as session:
        # Verify membership
        stmt = select(WorkspaceMembershipORM).where(
            WorkspaceMembershipORM.workspace_id == workspace_id,
            WorkspaceMembershipORM.user_id == current_user.id,
            WorkspaceMembershipORM.state == "active",
        )
        membership = (await session.execute(stmt)).scalar_one_or_none()
        if membership is None:
            raise HTTPException(
                status_code=http_status.HTTP_403_FORBIDDEN,
                detail={
                    "error": {
                        "code": "NOT_A_MEMBER",
                        "message": "you are not a member of this workspace",
                        "details": {},
                    }
                },
            )

        # Update session's active workspace
        from app.infrastructure.persistence.models.orm import UserORM

        user = await session.get(UserORM, current_user.id)
        if user is not None:
            user.last_chosen_workspace_id = workspace_id
            await session.commit()

    return {"data": {"workspace_id": str(workspace_id)}, "message": "ok"}
