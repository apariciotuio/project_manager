"""EP-08 — Team + TeamMembership + Notification."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.team import (
    Notification,
    NotificationState,
    Team,
    TeamMembership,
    TeamRole,
)


class TestTeam:
    def test_create_strips_name(self) -> None:
        t = Team.create(workspace_id=uuid4(), name="  platform  ", created_by=uuid4())
        assert t.name == "platform"
        assert t.deleted_at is None

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            Team.create(workspace_id=uuid4(), name="   ", created_by=uuid4())

    def test_long_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            Team.create(workspace_id=uuid4(), name="x" * 256, created_by=uuid4())

    def test_soft_delete_sets_timestamps(self) -> None:
        t = Team.create(workspace_id=uuid4(), name="n", created_by=uuid4())
        t.soft_delete()
        assert t.deleted_at is not None


class TestTeamMembership:
    def test_create_default_role_member(self) -> None:
        m = TeamMembership.create(team_id=uuid4(), user_id=uuid4())
        assert m.role is TeamRole.MEMBER
        assert m.removed_at is None

    def test_remove_sets_timestamp(self) -> None:
        m = TeamMembership.create(team_id=uuid4(), user_id=uuid4())
        m.remove()
        assert m.removed_at is not None


class TestNotification:
    def _make(self) -> Notification:
        return Notification.create(
            workspace_id=uuid4(),
            recipient_id=uuid4(),
            type="review.assigned",
            subject_type="review",
            subject_id=uuid4(),
            deeplink="/items/x/reviews/y",
            idempotency_key="evt-1",
        )

    def test_starts_unread(self) -> None:
        n = self._make()
        assert n.state is NotificationState.UNREAD
        assert n.read_at is None

    def test_mark_read_once(self) -> None:
        n = self._make()
        n.mark_read()
        first_time = n.read_at
        n.mark_read()  # idempotent on already-read
        assert n.state is NotificationState.READ
        assert n.read_at == first_time

    def test_mark_actioned_overrides(self) -> None:
        n = self._make()
        n.mark_actioned()
        assert n.state is NotificationState.ACTIONED
        assert n.actioned_at is not None
