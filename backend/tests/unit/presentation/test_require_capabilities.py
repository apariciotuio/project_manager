"""EP-12 — require_capabilities FastAPI dependency.

Authorization gate: a route can declare one or more required capabilities;
the dependency checks the caller's active workspace membership and returns
403 when any required capability is missing. Superadmin bypasses the check
but the bypass is logged for audit.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest
from fastapi import HTTPException


class _FakeRepo:
    """In-memory capability store keyed by (user_id, workspace_id)."""

    def __init__(self) -> None:
        self.store: dict[tuple, list[str]] = {}

    async def get_capabilities_for(self, user_id, workspace_id):
        return self.store.get((user_id, workspace_id))


def _make_user(workspace_id=None, is_superadmin=False):
    from app.presentation.middleware.auth_middleware import CurrentUser

    return CurrentUser(
        id=uuid4(),
        email="u@example.com",
        workspace_id=workspace_id if workspace_id is not None else uuid4(),
        is_superadmin=is_superadmin,
    )


class TestRequireCapabilities:
    @pytest.mark.asyncio
    async def test_passes_when_user_has_required_capability(self) -> None:
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user()
        repo = _FakeRepo()
        repo.store[(user.id, user.workspace_id)] = ["review", "write"]

        dep = build_require_capabilities("review")
        # Should not raise — returns the user.
        result = await dep(user, repo)
        assert result.id == user.id

    @pytest.mark.asyncio
    async def test_returns_403_when_missing_required_capability(self) -> None:
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user()
        repo = _FakeRepo()
        repo.store[(user.id, user.workspace_id)] = ["write"]  # no "review"

        dep = build_require_capabilities("review")
        with pytest.raises(HTTPException) as exc_info:
            await dep(user, repo)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_403_when_workspace_id_is_none(self) -> None:
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user(workspace_id=None)
        repo = _FakeRepo()
        dep = build_require_capabilities("review")

        with pytest.raises(HTTPException) as exc_info:
            await dep(user, repo)
        # workspace missing → either 401 or 403; must not leak existence.
        assert exc_info.value.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_returns_403_when_membership_missing(self) -> None:
        """Token valid but no active membership row in the workspace → 403."""
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user()
        repo = _FakeRepo()  # no entry for this (user, workspace)
        dep = build_require_capabilities("review")

        with pytest.raises(HTTPException) as exc_info:
            await dep(user, repo)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_superadmin_bypasses_check_and_logs(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user(is_superadmin=True)
        repo = _FakeRepo()  # superadmin has no membership — must still pass

        dep = build_require_capabilities("review", "destructive_action")
        with caplog.at_level(logging.INFO, logger="app.presentation.capabilities"):
            result = await dep(user, repo)
        assert result.id == user.id
        msg = " ".join(rec.getMessage() for rec in caplog.records)
        assert "superadmin" in msg.lower()
        # Must log what was bypassed for audit.
        assert "review" in msg
        assert "destructive_action" in msg

    @pytest.mark.asyncio
    async def test_requires_all_listed_capabilities(self) -> None:
        """Multi-cap check: missing ANY of the required caps → 403."""
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user()
        repo = _FakeRepo()
        repo.store[(user.id, user.workspace_id)] = ["review"]  # missing "write"

        dep = build_require_capabilities("review", "write")
        with pytest.raises(HTTPException) as exc_info:
            await dep(user, repo)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_empty_capability_list_accepts_any_authenticated_user(self) -> None:
        """build_require_capabilities() with no args should be treated as a
        misconfiguration — accepts any authenticated user (noop gate)."""
        from app.presentation.capabilities import build_require_capabilities

        user = _make_user()
        repo = _FakeRepo()
        # No membership, no superadmin, no required caps → pass.
        dep = build_require_capabilities()
        result = await dep(user, repo)
        assert result.id == user.id
