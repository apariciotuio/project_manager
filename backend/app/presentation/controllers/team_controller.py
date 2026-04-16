"""EP-08 — Team + TeamMembership controller.

Routes:
  POST   /api/v1/teams
  GET    /api/v1/teams
  GET    /api/v1/teams/{team_id}
  DELETE /api/v1/teams/{team_id}
  POST   /api/v1/teams/{team_id}/members
  DELETE /api/v1/teams/{team_id}/members/{user_id}
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from pydantic import BaseModel

from app.application.services.team_service import (
    MembershipAlreadyExistsError,
    MembershipNotFoundError,
    TeamAlreadyDeletedError,
    TeamNotFoundError,
    TeamService,
)
from app.domain.models.team import TeamRole
from app.presentation.dependencies import get_current_user, get_team_service
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["teams"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _team_payload(team: Any) -> dict[str, Any]:
    return {
        "id": str(team.id),
        "workspace_id": str(team.workspace_id),
        "name": team.name,
        "description": team.description,
        "can_receive_reviews": team.can_receive_reviews,
        "deleted_at": team.deleted_at.isoformat() if team.deleted_at else None,
        "created_at": team.created_at.isoformat(),
        "updated_at": team.updated_at.isoformat(),
        "created_by": str(team.created_by),
    }


def _membership_payload(m: Any) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "team_id": str(m.team_id),
        "user_id": str(m.user_id),
        "role": m.role.value,
        "joined_at": m.joined_at.isoformat(),
        "removed_at": m.removed_at.isoformat() if m.removed_at else None,
    }


class CreateTeamRequest(BaseModel):
    name: str
    description: str | None = None
    can_receive_reviews: bool = False


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: TeamRole = TeamRole.MEMBER


@router.post("/teams", status_code=http_status.HTTP_201_CREATED)
async def create_team(
    body: CreateTeamRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        team = await service.create(
            workspace_id=current_user.workspace_id,
            name=body.name,
            created_by=current_user.id,
            description=body.description,
            can_receive_reviews=body.can_receive_reviews,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_INPUT", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_team_payload(team), "team created")


@router.get("/teams")
async def list_teams(
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    teams = await service.list_for_workspace(current_user.workspace_id)
    return _ok([_team_payload(t) for t in teams])


@router.get("/teams/{team_id}")
async def get_team(
    team_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        team = await service.get(team_id)
    except TeamNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_team_payload(team))


@router.delete("/teams/{team_id}", status_code=http_status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> None:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        await service.soft_delete(team_id)
    except TeamNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except TeamAlreadyDeletedError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_DELETED", "message": str(exc), "details": {}}},
        ) from exc


@router.post("/teams/{team_id}/members", status_code=http_status.HTTP_201_CREATED)
async def add_member(
    team_id: UUID,
    body: AddMemberRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> dict[str, Any]:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        membership = await service.add_member(
            team_id=team_id, user_id=body.user_id, role=body.role
        )
    except TeamNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except MembershipAlreadyExistsError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "ALREADY_MEMBER", "message": str(exc), "details": {}}},
        ) from exc
    return _ok(_membership_payload(membership), "member added")


@router.delete(
    "/teams/{team_id}/members/{user_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    team_id: UUID,
    user_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    service: TeamService = Depends(get_team_service),
) -> None:
    if current_user.workspace_id is None:
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "NO_WORKSPACE", "message": "no workspace", "details": {}}},
        )
    try:
        await service.remove_member(team_id=team_id, user_id=user_id)
    except MembershipNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
