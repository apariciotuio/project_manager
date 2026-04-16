"""Unit tests for the WorkspaceMembership domain entity."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.models.workspace_membership import WorkspaceMembership


class TestCreate:
    def test_defaults_to_active_member(self) -> None:
        m = WorkspaceMembership.create(
            workspace_id=uuid4(), user_id=uuid4(), role="member", is_default=True
        )
        assert isinstance(m.id, UUID)
        assert m.role == "member"
        assert m.state == "active"
        assert m.is_default is True
        assert m.joined_at.tzinfo is not None

    def test_invited_state_is_allowed(self) -> None:
        m = WorkspaceMembership.create(
            workspace_id=uuid4(),
            user_id=uuid4(),
            role="member",
            is_default=False,
            state="invited",
        )
        assert m.state == "invited"
        assert m.is_active() is False

    @pytest.mark.parametrize("bad_role", ["", None, "   "])
    def test_rejects_empty_role(self, bad_role: str | None) -> None:
        with pytest.raises(ValueError, match="role"):
            WorkspaceMembership.create(
                workspace_id=uuid4(),
                user_id=uuid4(),
                role=bad_role,
                is_default=False,
            )

    @pytest.mark.parametrize("bad_state", ["unknown", "ACTIVE", "", None])
    def test_rejects_invalid_state(self, bad_state: str | None) -> None:
        with pytest.raises(ValueError, match="state"):
            WorkspaceMembership.create(
                workspace_id=uuid4(),
                user_id=uuid4(),
                role="member",
                is_default=False,
                state=bad_state,
            )


class TestLifecycle:
    def _active(self) -> WorkspaceMembership:
        return WorkspaceMembership.create(
            workspace_id=uuid4(), user_id=uuid4(), role="member", is_default=True
        )

    def test_active_membership_is_active(self) -> None:
        assert self._active().is_active() is True

    def test_suspend_blocks_activity(self) -> None:
        m = self._active()
        m.suspend()
        assert m.state == "suspended"
        assert m.is_active() is False

    def test_activate_restores_active(self) -> None:
        m = self._active()
        m.suspend()
        m.activate()
        assert m.state == "active"
        assert m.is_active() is True

    def test_cannot_activate_deleted(self) -> None:
        m = self._active()
        m.mark_deleted()
        with pytest.raises(ValueError, match="deleted"):
            m.activate()

    def test_mark_deleted_is_terminal(self) -> None:
        m = self._active()
        m.mark_deleted()
        assert m.state == "deleted"
        with pytest.raises(ValueError, match="deleted"):
            m.suspend()
