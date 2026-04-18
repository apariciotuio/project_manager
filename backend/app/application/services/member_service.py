"""MemberService — EP-10 admin member management.

Responsibilities:
- List members (with pagination + filters)
- Update member state (suspend/reactivate/delete)
- Update capabilities (with capability-check guard)
- Update context labels
- Invite new members (create invitation)
- Resend invitation
- Audit every mutation
"""
from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.services.audit_service import AuditService
from app.domain.models.invitation import Invitation
from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.repositories.invitation_repository import IInvitationRepository
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)
from app.infrastructure.pagination import PaginationCursor, PaginationResult
from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Capability constants
# ---------------------------------------------------------------------------

ALL_CAPABILITIES: frozenset[str] = frozenset(
    {
        "invite_members",
        "deactivate_members",
        "manage_teams",
        "configure_workspace_rules",
        "configure_project",
        "configure_integration",
        "view_audit_log",
        "view_admin_dashboard",
        "reassign_owner",
        "retry_exports",
        "force_unlock",
        "manage_tags",
        "merge_tags",
        "manage_puppet_integration",
    }
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class MemberNotFoundError(LookupError):
    pass


class DuplicateActiveMemberError(ValueError):
    code = "member_already_active"


class InvitePendingError(ValueError):
    code = "invite_pending"

    def __init__(self, invitation_id: UUID) -> None:
        super().__init__("invitation already pending")
        self.invitation_id = invitation_id


class CannotSuspendLastAdminError(ValueError):
    code = "cannot_suspend_last_admin"


class CannotGrantUnpossessedCapabilityError(ValueError):
    code = "cannot_grant_unpossessed_capability"


class InviteNotResendableError(ValueError):
    code = "invite_not_resendable"


class InvalidCapabilityError(ValueError):
    code = "invalid_capability"


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass
class MemberDTO:
    id: UUID
    user_id: UUID
    email: str
    display_name: str
    state: str
    role: str
    capabilities: list[str]
    context_labels: list[str]
    joined_at: datetime


@dataclass
class InviteResult:
    invitation_id: UUID
    resend_url: str | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class MemberService:
    def __init__(
        self,
        membership_repo: IWorkspaceMembershipRepository,
        invitation_repo: IInvitationRepository,
        audit: AuditService,
        # session injected for raw queries (admin list with user join)
        session: object,
    ) -> None:
        self._membership_repo = membership_repo
        self._invitation_repo = invitation_repo
        self._audit = audit
        self._session = session

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_members(
        self,
        workspace_id: UUID,
        *,
        state: str | None = None,
        teamless: bool = False,
        cursor: PaginationCursor | None = None,
        limit: int = 50,
    ) -> PaginationResult:
        from sqlalchemy import select, and_, or_
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import (
            WorkspaceMembershipORM,
            UserORM,
            TeamMembershipORM,
        )

        session: AsyncSession = self._session  # type: ignore[assignment]

        stmt = (
            select(WorkspaceMembershipORM, UserORM)
            .join(UserORM, WorkspaceMembershipORM.user_id == UserORM.id)
            .where(WorkspaceMembershipORM.workspace_id == workspace_id)
        )

        if state:
            stmt = stmt.where(WorkspaceMembershipORM.state == state)

        if teamless:
            # Members with no active team membership
            subq = select(TeamMembershipORM.user_id).where(
                TeamMembershipORM.workspace_id == workspace_id
            ).distinct()
            stmt = stmt.where(WorkspaceMembershipORM.user_id.not_in(subq))

        if cursor is not None:
            stmt = stmt.where(
                or_(
                    WorkspaceMembershipORM.joined_at < cursor.created_at,
                    and_(
                        WorkspaceMembershipORM.joined_at == cursor.created_at,
                        WorkspaceMembershipORM.id < cursor.id,
                    ),
                )
            )

        effective_limit = min(limit, 200)
        stmt = stmt.order_by(
            WorkspaceMembershipORM.joined_at.desc(),
            WorkspaceMembershipORM.id.desc(),
        ).limit(effective_limit + 1)

        rows = (await session.execute(stmt)).all()

        has_next = len(rows) > effective_limit
        page_rows = rows[:effective_limit]

        items: list[MemberDTO] = []
        for membership_row, user_row in page_rows:
            items.append(
                MemberDTO(
                    id=membership_row.id,
                    user_id=user_row.id,
                    email=user_row.email,
                    display_name=user_row.full_name,
                    state=membership_row.state,
                    role=membership_row.role,
                    capabilities=list(membership_row.capabilities or []),
                    context_labels=list(membership_row.context_labels or []),
                    joined_at=membership_row.joined_at,
                )
            )

        next_cursor: str | None = None
        if has_next and page_rows:
            last_membership = page_rows[-1][0]
            next_cursor = PaginationCursor(
                id=last_membership.id,
                created_at=last_membership.joined_at,
            ).encode()

        return PaginationResult(
            rows=items,  # type: ignore[arg-type]
            has_next=has_next,
            next_cursor=next_cursor,
        )

    # ------------------------------------------------------------------
    # Invite
    # ------------------------------------------------------------------

    async def invite_member(
        self,
        workspace_id: UUID,
        *,
        email: str,
        context_labels: list[str],
        team_ids: list[UUID],
        initial_capabilities: list[str],
        actor_id: UUID,
        actor_workspace_id: UUID,
    ) -> InviteResult:
        email = email.lower().strip()

        # Check for existing active membership
        existing = await self._get_active_membership_by_email(workspace_id, email)
        if existing is not None:
            raise DuplicateActiveMemberError(email)

        # Check for pending invitation
        pending = await self._invitation_repo.get_active_by_email(workspace_id, email)
        if pending is not None and not pending.is_expired():
            raise InvitePendingError(pending.id)

        # Validate capabilities
        unknown = set(initial_capabilities) - ALL_CAPABILITIES
        if unknown:
            raise InvalidCapabilityError(f"unknown capabilities: {sorted(unknown)}")

        token = _generate_invite_token()
        token_hash = _hash_token(token)

        invitation = Invitation.create(
            workspace_id=workspace_id,
            email=email,
            token_hash=token_hash,
            context_labels=context_labels,
            team_ids=team_ids,
            initial_capabilities=initial_capabilities,
            created_by=actor_id,
        )
        await self._invitation_repo.create(invitation)

        await self._audit.log_event(
            category="admin",
            action="member_invited",
            actor_id=actor_id,
            workspace_id=actor_workspace_id,
            entity_type="invitation",
            entity_id=invitation.id,
            context={"email": email},
        )

        return InviteResult(invitation_id=invitation.id)

    # ------------------------------------------------------------------
    # Update state
    # ------------------------------------------------------------------

    async def update_member(
        self,
        workspace_id: UUID,
        membership_id: UUID,
        *,
        state: str | None = None,
        capabilities: list[str] | None = None,
        context_labels: list[str] | None = None,
        actor_id: UUID,
        actor_capabilities: list[str],
    ) -> WorkspaceMembership:
        membership = await self._get_membership(workspace_id, membership_id)
        before: dict[str, object] = {
            "state": membership.state,
            "capabilities": list(membership.capabilities if hasattr(membership, "capabilities") else []),
        }

        from sqlalchemy.ext.asyncio import AsyncSession
        from sqlalchemy import select
        from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        row = (
            await session.execute(
                select(WorkspaceMembershipORM).where(
                    WorkspaceMembershipORM.id == membership_id,
                    WorkspaceMembershipORM.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            raise MemberNotFoundError(membership_id)

        if state == "suspended":
            await self._guard_last_admin(workspace_id, membership_id, session)
            row.state = "suspended"
        elif state == "active":
            row.state = "active"
        elif state == "deleted":
            await self._guard_last_admin(workspace_id, membership_id, session)
            row.state = "deleted"

        if capabilities is not None:
            unknown = set(capabilities) - ALL_CAPABILITIES
            if unknown:
                raise InvalidCapabilityError(f"unknown capabilities: {sorted(unknown)}")
            # Can only grant capabilities you possess (unless superadmin)
            new_caps = set(capabilities)
            granted = new_caps - set(row.capabilities or [])
            actor_caps = set(actor_capabilities)
            unpossessed = granted - actor_caps
            if unpossessed and "view_admin_dashboard" not in actor_capabilities:
                # superadmin check done at controller level; here check capability delegation
                raise CannotGrantUnpossessedCapabilityError(
                    f"cannot grant capabilities you don't possess: {sorted(unpossessed)}"
                )
            row.capabilities = list(capabilities)

        if context_labels is not None:
            row.context_labels = list(context_labels)

        await session.flush()

        await self._audit.log_event(
            category="admin",
            action="member_updated",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="workspace_membership",
            entity_id=membership_id,
            before_value=before,
            after_value={
                "state": row.state,
                "capabilities": list(row.capabilities or []),
            },
        )

        return WorkspaceMembership(
            id=row.id,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.role,
            state=row.state,  # type: ignore[arg-type]
            is_default=row.is_default,
            joined_at=row.joined_at,
        )

    # ------------------------------------------------------------------
    # Resend invitation
    # ------------------------------------------------------------------

    async def resend_invitation(
        self,
        workspace_id: UUID,
        invitation_id: UUID,
        actor_id: UUID,
    ) -> Invitation:
        invitation = await self._invitation_repo.get_by_id(invitation_id)
        if invitation is None or invitation.workspace_id != workspace_id:
            from app.domain.repositories.invitation_repository import IInvitationRepository
            raise MemberNotFoundError(invitation_id)

        if not invitation.is_resendable():
            raise InviteNotResendableError(invitation_id)

        new_token = _generate_invite_token()
        invitation.refresh_token(_hash_token(new_token))
        await self._invitation_repo.save(invitation)

        await self._audit.log_event(
            category="admin",
            action="invitation_resent",
            actor_id=actor_id,
            workspace_id=workspace_id,
            entity_type="invitation",
            entity_id=invitation_id,
            context={"email": invitation.email},
        )
        return invitation

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_membership(
        self, workspace_id: UUID, membership_id: UUID
    ) -> WorkspaceMembership:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        row = (
            await session.execute(
                select(WorkspaceMembershipORM).where(
                    WorkspaceMembershipORM.id == membership_id,
                    WorkspaceMembershipORM.workspace_id == workspace_id,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            raise MemberNotFoundError(membership_id)
        return WorkspaceMembership(
            id=row.id,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.role,
            state=row.state,  # type: ignore[arg-type]
            is_default=row.is_default,
            joined_at=row.joined_at,
        )

    async def _get_active_membership_by_email(
        self, workspace_id: UUID, email: str
    ) -> WorkspaceMembership | None:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM, UserORM

        session: AsyncSession = self._session  # type: ignore[assignment]
        stmt = (
            select(WorkspaceMembershipORM)
            .join(UserORM, WorkspaceMembershipORM.user_id == UserORM.id)
            .where(
                WorkspaceMembershipORM.workspace_id == workspace_id,
                WorkspaceMembershipORM.state == "active",
                UserORM.email == email,
            )
            .limit(1)
        )
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return WorkspaceMembership(
            id=row.id,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.role,
            state=row.state,  # type: ignore[arg-type]
            is_default=row.is_default,
            joined_at=row.joined_at,
        )

    async def _guard_last_admin(
        self, workspace_id: UUID, membership_id: UUID, session: object
    ) -> None:
        from sqlalchemy import select, func
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.infrastructure.persistence.models.orm import WorkspaceMembershipORM

        s: AsyncSession = session  # type: ignore[assignment]
        count_stmt = select(func.count()).where(
            WorkspaceMembershipORM.workspace_id == workspace_id,
            WorkspaceMembershipORM.role.in_(["admin", "workspace_admin"]),
            WorkspaceMembershipORM.state == "active",
            WorkspaceMembershipORM.id != membership_id,
        )
        count = (await s.execute(count_stmt)).scalar_one()
        if count == 0:
            raise CannotSuspendLastAdminError("cannot suspend the last workspace admin")


def _generate_invite_token() -> str:
    return os.urandom(32).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
