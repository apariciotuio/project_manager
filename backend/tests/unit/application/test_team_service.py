"""EP-08 — Unit tests for TeamService guards (A1.4, A3.2, A3.3, A3.4, A3.5).

RED phase: write failing tests for:
- LastLeadError on remove_member when target is last lead
- LastLeadError on update_role when demoting last lead
- add_member: suspended user re-add is idempotent re-activation
- soft_delete: open reviews guard raises TeamHasOpenReviewsError
- update_role: happy path promotes / demotes
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.models.team import Team, TeamMembership, TeamRole

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeTeamRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Team] = {}

    async def create(self, team: Team) -> Team:
        self._store[team.id] = team
        return team

    async def get(self, team_id: UUID) -> Team | None:
        return self._store.get(team_id)

    async def list_active_for_workspace(self, workspace_id: UUID) -> list[Team]:
        return [t for t in self._store.values() if t.deleted_at is None and t.workspace_id == workspace_id]

    async def save(self, team: Team) -> Team:
        self._store[team.id] = team
        return team


class FakeMembershipRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, TeamMembership] = {}
        # Track suspended user ids
        self._suspended: set[UUID] = set()

    def mark_suspended(self, user_id: UUID) -> None:
        self._suspended.add(user_id)

    def is_suspended(self, user_id: UUID) -> bool:
        return user_id in self._suspended

    async def add_member(self, membership: TeamMembership) -> TeamMembership:
        self._store[membership.id] = membership
        return membership

    async def get_active(self, team_id: UUID, user_id: UUID) -> TeamMembership | None:
        for m in self._store.values():
            if m.team_id == team_id and m.user_id == user_id and m.removed_at is None:
                return m
        return None

    async def get_any(self, team_id: UUID, user_id: UUID) -> TeamMembership | None:
        """Return most recent membership (active or removed) for a user."""
        matches = [
            m for m in self._store.values()
            if m.team_id == team_id and m.user_id == user_id
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda m: m.joined_at, reverse=True)[0]

    async def save(self, membership: TeamMembership) -> TeamMembership:
        self._store[membership.id] = membership
        return membership

    async def list_for_team(self, team_id: UUID) -> list[TeamMembership]:
        return [m for m in self._store.values() if m.team_id == team_id]

    async def list_teams_for_user(self, user_id: UUID, workspace_id: UUID) -> list[Team]:
        return []

    async def list_active_members_with_users(self, team_ids: list[UUID]) -> dict[UUID, list]:
        return {}

    async def count_active_leads(self, team_id: UUID) -> int:
        return sum(
            1
            for m in self._store.values()
            if m.team_id == team_id and m.role == TeamRole.LEAD and m.removed_at is None
        )


class FakeReviewRequestRepository:
    def __init__(self) -> None:
        self._open_teams: set[UUID] = set()

    def mark_has_open_reviews(self, team_id: UUID) -> None:
        self._open_teams.add(team_id)

    async def has_open_reviews_for_team(self, team_id: UUID) -> bool:
        return team_id in self._open_teams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team(workspace_id: UUID | None = None) -> Team:
    return Team.create(
        workspace_id=workspace_id or uuid4(),
        name="alpha team",
        created_by=uuid4(),
    )


def _make_membership(team_id: UUID, user_id: UUID, role: TeamRole = TeamRole.MEMBER) -> TeamMembership:
    m = TeamMembership.create(team_id=team_id, user_id=user_id, role=role)
    return m


# ---------------------------------------------------------------------------
# Tests — LastLeadError on remove_member
# ---------------------------------------------------------------------------


class TestRemoveMemberLastLead:
    @pytest.mark.asyncio
    async def test_remove_last_lead_raises_last_lead_error(self) -> None:
        from app.application.services.team_service import LastLeadError, TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead_id = uuid4()
        lead_membership = _make_membership(team.id, lead_id, TeamRole.LEAD)
        await membership_repo.add_member(lead_membership)

        with pytest.raises(LastLeadError):
            await svc.remove_member(team_id=team.id, user_id=lead_id)

    @pytest.mark.asyncio
    async def test_remove_member_when_another_lead_exists_succeeds(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead1_id, lead2_id = uuid4(), uuid4()
        await membership_repo.add_member(_make_membership(team.id, lead1_id, TeamRole.LEAD))
        await membership_repo.add_member(_make_membership(team.id, lead2_id, TeamRole.LEAD))

        # Removing one lead is fine since another exists
        result = await svc.remove_member(team_id=team.id, user_id=lead1_id)
        assert result.removed_at is not None

    @pytest.mark.asyncio
    async def test_remove_non_lead_member_always_succeeds(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead_id, member_id = uuid4(), uuid4()
        await membership_repo.add_member(_make_membership(team.id, lead_id, TeamRole.LEAD))
        await membership_repo.add_member(_make_membership(team.id, member_id, TeamRole.MEMBER))

        result = await svc.remove_member(team_id=team.id, user_id=member_id)
        assert result.removed_at is not None


# ---------------------------------------------------------------------------
# Tests — update_role
# ---------------------------------------------------------------------------


class TestUpdateRole:
    @pytest.mark.asyncio
    async def test_update_role_demoting_last_lead_raises_last_lead_error(self) -> None:
        from app.application.services.team_service import LastLeadError, TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead_id = uuid4()
        await membership_repo.add_member(_make_membership(team.id, lead_id, TeamRole.LEAD))

        with pytest.raises(LastLeadError):
            await svc.update_role(team_id=team.id, user_id=lead_id, new_role=TeamRole.MEMBER)

    @pytest.mark.asyncio
    async def test_update_role_demote_lead_when_another_lead_exists_succeeds(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead1_id, lead2_id = uuid4(), uuid4()
        await membership_repo.add_member(_make_membership(team.id, lead1_id, TeamRole.LEAD))
        await membership_repo.add_member(_make_membership(team.id, lead2_id, TeamRole.LEAD))

        result = await svc.update_role(team_id=team.id, user_id=lead1_id, new_role=TeamRole.MEMBER)
        assert result.role == TeamRole.MEMBER

    @pytest.mark.asyncio
    async def test_update_role_promote_member_to_lead_succeeds(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        lead_id, member_id = uuid4(), uuid4()
        await membership_repo.add_member(_make_membership(team.id, lead_id, TeamRole.LEAD))
        await membership_repo.add_member(_make_membership(team.id, member_id, TeamRole.MEMBER))

        result = await svc.update_role(team_id=team.id, user_id=member_id, new_role=TeamRole.LEAD)
        assert result.role == TeamRole.LEAD


# ---------------------------------------------------------------------------
# Tests — add_member suspended idempotency (A3.2)
# ---------------------------------------------------------------------------


class TestAddMemberSuspended:
    @pytest.mark.asyncio
    async def test_add_suspended_user_raises_validation_error(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()

        suspended_user_id = uuid4()
        membership_repo.mark_suspended(suspended_user_id)

        svc = TeamService(
            team_repo=team_repo,
            membership_repo=membership_repo,
            review_repo=review_repo,
            is_user_suspended=membership_repo.is_suspended,
        )

        team = await team_repo.create(_make_team())

        with pytest.raises(ValueError, match="suspended"):
            await svc.add_member(team_id=team.id, user_id=suspended_user_id)

    @pytest.mark.asyncio
    async def test_readd_suspended_then_active_user_reactivates(self) -> None:
        """Re-adding a previously suspended (removed) user is idempotent re-activation."""
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        user_id = uuid4()

        # Add, then remove (simulate suspended/removed state)
        m = _make_membership(team.id, user_id, TeamRole.MEMBER)
        await membership_repo.add_member(m)
        m.remove()
        await membership_repo.save(m)

        # Re-add: should reactivate, not conflict
        result = await svc.add_member(team_id=team.id, user_id=user_id)
        assert result.removed_at is None
        assert result.team_id == team.id


# ---------------------------------------------------------------------------
# Tests — soft_delete open reviews guard (A3.5)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests — TeamService.create (A3.1)
# ---------------------------------------------------------------------------


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_returns_team(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        ws_id = uuid4()
        creator_id = uuid4()
        team = await svc.create(
            workspace_id=ws_id,
            name="Alpha",
            created_by=creator_id,
        )

        assert team.name == "Alpha"
        assert team.workspace_id == ws_id
        assert team.created_by == creator_id
        assert team.deleted_at is None

    @pytest.mark.asyncio
    async def test_create_empty_name_raises_invariant_error(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        with pytest.raises(ValueError):
            await svc.create(
                workspace_id=uuid4(),
                name="   ",
                created_by=uuid4(),
            )

    @pytest.mark.asyncio
    async def test_get_returns_team_in_workspace(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        ws_id = uuid4()
        team = await team_repo.create(_make_team(ws_id))

        result = await svc.get(team.id, workspace_id=ws_id)
        assert result.id == team.id

    @pytest.mark.asyncio
    async def test_get_cross_workspace_raises_not_found(self) -> None:
        from app.application.services.team_service import TeamNotFoundError, TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        ws_id = uuid4()
        other_ws_id = uuid4()
        team = await team_repo.create(_make_team(ws_id))

        with pytest.raises(TeamNotFoundError):
            await svc.get(team.id, workspace_id=other_ws_id)


class TestSoftDeleteOpenReviews:
    @pytest.mark.asyncio
    async def test_soft_delete_with_open_reviews_raises(self) -> None:
        from app.application.services.team_service import TeamHasOpenReviewsError, TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())
        review_repo.mark_has_open_reviews(team.id)

        with pytest.raises(TeamHasOpenReviewsError):
            await svc.soft_delete(team.id)

    @pytest.mark.asyncio
    async def test_soft_delete_without_open_reviews_succeeds(self) -> None:
        from app.application.services.team_service import TeamService

        team_repo = FakeTeamRepository()
        membership_repo = FakeMembershipRepository()
        review_repo = FakeReviewRequestRepository()
        svc = TeamService(team_repo=team_repo, membership_repo=membership_repo, review_repo=review_repo)

        team = await team_repo.create(_make_team())

        result = await svc.soft_delete(team.id)
        assert result.deleted_at is not None
