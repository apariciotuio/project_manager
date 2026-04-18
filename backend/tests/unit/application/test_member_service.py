"""Unit tests for MemberService — EP-10 admin members."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.member_service import (
    ALL_CAPABILITIES,
    CannotGrantUnpossessedCapabilityError,
    CannotSuspendLastAdminError,
    DuplicateActiveMemberError,
    InvitePendingError,
    InviteNotResendableError,
    InvalidCapabilityError,
    MemberNotFoundError,
    MemberService,
)
from app.domain.models.invitation import Invitation
from app.domain.models.workspace_membership import WorkspaceMembership
from app.domain.repositories.invitation_repository import IInvitationRepository
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeInvitationRepo(IInvitationRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, Invitation] = {}
        self._by_email: dict[tuple[UUID, str], Invitation] = {}

    async def create(self, invitation: Invitation) -> Invitation:
        self._by_id[invitation.id] = invitation
        self._by_email[(invitation.workspace_id, invitation.email)] = invitation
        return invitation

    async def get_by_id(self, invitation_id: UUID) -> Invitation | None:
        return self._by_id.get(invitation_id)

    async def get_by_token_hash(self, token_hash: str) -> Invitation | None:
        return next((i for i in self._by_id.values() if i.token_hash == token_hash), None)

    async def get_active_by_email(self, workspace_id: UUID, email: str) -> Invitation | None:
        return self._by_email.get((workspace_id, email))

    async def save(self, invitation: Invitation) -> Invitation:
        self._by_id[invitation.id] = invitation
        return invitation

    async def list_for_workspace(self, workspace_id: UUID, *, state: str | None = None) -> list[Invitation]:
        result = [i for i in self._by_id.values() if i.workspace_id == workspace_id]
        if state:
            result = [i for i in result if i.state == state]
        return result


class FakeMembershipRepo(IWorkspaceMembershipRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, WorkspaceMembership] = {}

    async def create(self, membership: WorkspaceMembership) -> WorkspaceMembership:
        self._by_id[membership.id] = membership
        return membership

    async def get_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        return [m for m in self._by_id.values() if m.user_id == user_id]

    async def get_active_by_user_id(self, user_id: UUID) -> list[WorkspaceMembership]:
        return [m for m in self._by_id.values() if m.user_id == user_id and m.state == "active"]

    async def get_for_user_and_workspace(self, user_id: UUID, workspace_id: UUID) -> WorkspaceMembership | None:
        return next(
            (m for m in self._by_id.values()
             if m.user_id == user_id and m.workspace_id == workspace_id and m.state == "active"),
            None,
        )

    async def get_default_for_user(self, user_id: UUID) -> WorkspaceMembership | None:
        return next(
            (m for m in self._by_id.values() if m.user_id == user_id and m.is_default),
            None,
        )


class FakeAuditService:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_WS_ID = uuid4()
_ACTOR_ID = uuid4()


def _make_service(invitation_repo: FakeInvitationRepo | None = None) -> tuple[MemberService, FakeAuditService]:
    inv_repo = invitation_repo or FakeInvitationRepo()
    audit = FakeAuditService()

    # Fake SQLAlchemy session that returns nothing
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None),
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
        all=MagicMock(return_value=[]),
    ))
    session.flush = AsyncMock()

    svc = MemberService(
        membership_repo=FakeMembershipRepo(),
        invitation_repo=inv_repo,
        audit=audit,  # type: ignore[arg-type]
        session=session,
    )
    return svc, audit


# ---------------------------------------------------------------------------
# Tests: invite_member
# ---------------------------------------------------------------------------


class TestInviteMember:
    @pytest.mark.asyncio
    async def test_invite_success_creates_invitation(self) -> None:
        inv_repo = FakeInvitationRepo()
        svc, audit = _make_service(inv_repo)

        result = await svc.invite_member(
            _WS_ID,
            email="new@example.com",
            context_labels=[],
            team_ids=[],
            initial_capabilities=[],
            actor_id=_ACTOR_ID,
            actor_workspace_id=_WS_ID,
        )

        assert result.invitation_id is not None
        assert len(inv_repo._by_id) == 1
        assert len(audit.events) == 1
        assert audit.events[0]["action"] == "member_invited"

    @pytest.mark.asyncio
    async def test_invite_duplicate_active_raises_409(self) -> None:
        inv_repo = FakeInvitationRepo()
        svc, _ = _make_service(inv_repo)

        # Simulate existing active membership via session mock
        from unittest.mock import AsyncMock, MagicMock
        existing_row = MagicMock()
        existing_row.id = uuid4()
        existing_row.workspace_id = _WS_ID
        existing_row.user_id = uuid4()
        existing_row.role = "member"
        existing_row.state = "active"
        existing_row.is_default = True
        from datetime import UTC, datetime
        existing_row.joined_at = datetime.now(UTC)
        svc._session.execute = AsyncMock(return_value=MagicMock(
            scalar_one_or_none=MagicMock(return_value=existing_row)
        ))

        with pytest.raises(DuplicateActiveMemberError):
            await svc.invite_member(
                _WS_ID,
                email="existing@example.com",
                context_labels=[],
                team_ids=[],
                initial_capabilities=[],
                actor_id=_ACTOR_ID,
                actor_workspace_id=_WS_ID,
            )

    @pytest.mark.asyncio
    async def test_invite_pending_raises_invite_pending(self) -> None:
        inv_repo = FakeInvitationRepo()
        # Pre-seed an existing pending invitation
        pending = Invitation.create(
            workspace_id=_WS_ID,
            email="pending@example.com",
            token_hash="hash123",
            context_labels=[],
            team_ids=[],
            initial_capabilities=[],
            created_by=_ACTOR_ID,
        )
        await inv_repo.create(pending)

        svc, _ = _make_service(inv_repo)

        with pytest.raises(InvitePendingError) as exc_info:
            await svc.invite_member(
                _WS_ID,
                email="pending@example.com",
                context_labels=[],
                team_ids=[],
                initial_capabilities=[],
                actor_id=_ACTOR_ID,
                actor_workspace_id=_WS_ID,
            )

        assert exc_info.value.invitation_id == pending.id

    @pytest.mark.asyncio
    async def test_invite_unknown_capability_raises_422(self) -> None:
        svc, _ = _make_service()

        with pytest.raises(InvalidCapabilityError):
            await svc.invite_member(
                _WS_ID,
                email="new@example.com",
                context_labels=[],
                team_ids=[],
                initial_capabilities=["fly_to_moon"],
                actor_id=_ACTOR_ID,
                actor_workspace_id=_WS_ID,
            )

    @pytest.mark.asyncio
    async def test_invite_all_valid_capabilities_accepted(self) -> None:
        inv_repo = FakeInvitationRepo()
        svc, _ = _make_service(inv_repo)

        result = await svc.invite_member(
            _WS_ID,
            email="cap@example.com",
            context_labels=[],
            team_ids=[],
            initial_capabilities=["invite_members", "manage_teams"],
            actor_id=_ACTOR_ID,
            actor_workspace_id=_WS_ID,
        )

        saved = list(inv_repo._by_id.values())[0]
        assert "invite_members" in saved.initial_capabilities
        assert "manage_teams" in saved.initial_capabilities


# ---------------------------------------------------------------------------
# Tests: resend_invitation
# ---------------------------------------------------------------------------


class TestResendInvitation:
    @pytest.mark.asyncio
    async def test_resend_success_refreshes_token(self) -> None:
        inv_repo = FakeInvitationRepo()
        invitation = Invitation.create(
            workspace_id=_WS_ID,
            email="user@example.com",
            token_hash="original_hash",
            context_labels=[],
            team_ids=[],
            initial_capabilities=[],
            created_by=_ACTOR_ID,
        )
        await inv_repo.create(invitation)
        svc, audit = _make_service(inv_repo)

        await svc.resend_invitation(_WS_ID, invitation.id, _ACTOR_ID)

        updated = inv_repo._by_id[invitation.id]
        assert updated.token_hash != "original_hash"
        assert any(e["action"] == "invitation_resent" for e in audit.events)

    @pytest.mark.asyncio
    async def test_resend_accepted_invitation_raises_not_resendable(self) -> None:
        inv_repo = FakeInvitationRepo()
        invitation = Invitation.create(
            workspace_id=_WS_ID,
            email="accepted@example.com",
            token_hash="hash",
            context_labels=[],
            team_ids=[],
            initial_capabilities=[],
            created_by=_ACTOR_ID,
        )
        invitation.accept()
        await inv_repo.create(invitation)
        svc, _ = _make_service(inv_repo)

        with pytest.raises(InviteNotResendableError):
            await svc.resend_invitation(_WS_ID, invitation.id, _ACTOR_ID)

    @pytest.mark.asyncio
    async def test_resend_wrong_workspace_raises_not_found(self) -> None:
        inv_repo = FakeInvitationRepo()
        invitation = Invitation.create(
            workspace_id=_WS_ID,
            email="user@example.com",
            token_hash="hash",
            context_labels=[],
            team_ids=[],
            initial_capabilities=[],
            created_by=_ACTOR_ID,
        )
        await inv_repo.create(invitation)
        svc, _ = _make_service(inv_repo)

        wrong_ws = uuid4()
        with pytest.raises(MemberNotFoundError):
            await svc.resend_invitation(wrong_ws, invitation.id, _ACTOR_ID)
