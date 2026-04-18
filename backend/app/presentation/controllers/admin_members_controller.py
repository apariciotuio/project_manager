"""EP-10 — Admin members controller.

Routes:
  GET    /api/v1/admin/members
  POST   /api/v1/admin/members
  PATCH  /api/v1/admin/members/{id}
  POST   /api/v1/admin/members/invitations/{id}/resend
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.audit_service import AuditService
from app.application.services.member_service import (
    CannotGrantUnpossessedCapabilityError,
    CannotSuspendLastAdminError,
    DuplicateActiveMemberError,
    InvitePendingError,
    InviteNotResendableError,
    InvalidCapabilityError,
    MemberNotFoundError,
    MemberService,
    ALL_CAPABILITIES,
)
from app.infrastructure.pagination import InvalidCursorError, PaginationCursor
from app.infrastructure.persistence.invitation_repository_impl import InvitationRepositoryImpl
from app.infrastructure.persistence.workspace_membership_repository_impl import (
    WorkspaceMembershipRepositoryImpl,
)
from app.presentation.dependencies import get_audit_service, get_db_session, require_admin
from app.presentation.middleware.auth_middleware import CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/members", tags=["admin-members"])


def _ok(data: object, message: str = "ok") -> dict[str, Any]:
    return {"data": data, "message": message}


def _member_payload(m: Any) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "user_id": str(m.user_id),
        "email": m.email,
        "display_name": m.display_name,
        "state": m.state,
        "role": m.role,
        "capabilities": m.capabilities,
        "context_labels": m.context_labels,
        "joined_at": m.joined_at.isoformat(),
    }


def get_member_service(
    session: AsyncSession = Depends(get_db_session),
    audit: AuditService = Depends(get_audit_service),
) -> MemberService:
    return MemberService(
        membership_repo=WorkspaceMembershipRepositoryImpl(session),
        invitation_repo=InvitationRepositoryImpl(session),
        audit=audit,
        session=session,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=None)
async def list_members(
    state: str | None = Query(default=None),
    teamless: bool = Query(default=False),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: CurrentUser = Depends(require_admin),
    service: MemberService = Depends(get_member_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None

    decoded_cursor: PaginationCursor | None = None
    if cursor:
        try:
            decoded_cursor = PaginationCursor.decode(cursor)
        except InvalidCursorError as exc:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": {"code": "INVALID_CURSOR", "message": str(exc), "details": {}}},
            ) from exc

    result = await service.list_members(
        current_user.workspace_id,
        state=state,
        teamless=teamless,
        cursor=decoded_cursor,
        limit=limit,
    )
    return _ok(
        {
            "items": [_member_payload(m) for m in result.rows],
            "pagination": {
                "cursor": result.next_cursor,
                "has_next": result.has_next,
            },
        }
    )


class InviteMemberRequest(BaseModel):
    email: EmailStr
    context_labels: list[str] = []
    team_ids: list[UUID] = []
    initial_capabilities: list[str] = []


@router.post("", status_code=http_status.HTTP_201_CREATED)
async def invite_member(
    body: InviteMemberRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: MemberService = Depends(get_member_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        result = await service.invite_member(
            current_user.workspace_id,
            email=str(body.email),
            context_labels=body.context_labels,
            team_ids=body.team_ids,
            initial_capabilities=body.initial_capabilities,
            actor_id=current_user.id,
            actor_workspace_id=current_user.workspace_id,
        )
    except DuplicateActiveMemberError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "member_already_active", "message": str(exc), "details": {}}},
        ) from exc
    except InvitePendingError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={
                "error": {
                    "code": "invite_pending",
                    "message": "invitation already pending",
                    "details": {
                        "invitation_id": str(exc.invitation_id),
                        "resend_url": f"/api/v1/admin/members/invitations/{exc.invitation_id}/resend",
                    },
                }
            },
        ) from exc
    except InvalidCapabilityError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_CAPABILITY", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({"invitation_id": str(result.invitation_id)}, "invitation sent")


class PatchMemberRequest(BaseModel):
    state: str | None = None
    capabilities: list[str] | None = None
    context_labels: list[str] | None = None


@router.patch("/{membership_id}")
async def update_member(
    membership_id: UUID,
    body: PatchMemberRequest,
    current_user: CurrentUser = Depends(require_admin),
    service: MemberService = Depends(get_member_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        actor_capabilities = await _get_actor_capabilities(service, current_user)
        updated = await service.update_member(
            current_user.workspace_id,
            membership_id,
            state=body.state,
            capabilities=body.capabilities,
            context_labels=body.context_labels,
            actor_id=current_user.id,
            actor_capabilities=actor_capabilities,
        )
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except CannotSuspendLastAdminError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "cannot_suspend_last_admin", "message": str(exc), "details": {}}},
        ) from exc
    except CannotGrantUnpossessedCapabilityError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "cannot_grant_unpossessed_capability", "message": str(exc), "details": {}}},
        ) from exc
    except InvalidCapabilityError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": {"code": "INVALID_CAPABILITY", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({"id": str(updated.id), "state": updated.state}, "member updated")


@router.post("/invitations/{invitation_id}/resend", status_code=http_status.HTTP_202_ACCEPTED)
async def resend_invitation(
    invitation_id: UUID,
    current_user: CurrentUser = Depends(require_admin),
    service: MemberService = Depends(get_member_service),
) -> dict[str, Any]:
    assert current_user.workspace_id is not None
    try:
        await service.resend_invitation(
            current_user.workspace_id, invitation_id, current_user.id
        )
    except MemberNotFoundError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "NOT_FOUND", "message": str(exc), "details": {}}},
        ) from exc
    except InviteNotResendableError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail={"error": {"code": "invite_not_resendable", "message": str(exc), "details": {}}},
        ) from exc
    return _ok({}, "invitation resent")


async def _get_actor_capabilities(service: MemberService, current_user: CurrentUser) -> list[str]:
    if current_user.is_superadmin:
        return list(ALL_CAPABILITIES)
    from sqlalchemy import select
    from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

    session = service._session
    row = (
        await session.execute(
            select(WorkspaceMembershipORM).where(
                WorkspaceMembershipORM.workspace_id == current_user.workspace_id,
                WorkspaceMembershipORM.user_id == current_user.id,
                WorkspaceMembershipORM.state == "active",
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return []
    return list(row.capabilities or [])
