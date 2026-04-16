"""Smoke tests for EP-00 repository interfaces.

These are ABCs — the only behavior to verify is that they reject direct instantiation.
Integration tests against the real implementations live under `tests/integration/`.
"""

from __future__ import annotations

import pytest

from app.domain.repositories.oauth_state_repository import IOAuthStateRepository
from app.domain.repositories.session_repository import ISessionRepository
from app.domain.repositories.user_repository import IUserRepository
from app.domain.repositories.workspace_membership_repository import (
    IWorkspaceMembershipRepository,
)
from app.domain.repositories.workspace_repository import IWorkspaceRepository


@pytest.mark.parametrize(
    "iface",
    [
        IUserRepository,
        ISessionRepository,
        IWorkspaceRepository,
        IWorkspaceMembershipRepository,
        IOAuthStateRepository,
    ],
)
def test_cannot_instantiate_abstract_repository(iface: type) -> None:
    with pytest.raises(TypeError, match="abstract"):
        iface()  # type: ignore[abstract]
