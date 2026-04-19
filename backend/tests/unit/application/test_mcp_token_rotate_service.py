"""Unit tests for MCPTokenRotateService — EP-18 Capability 1."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.mcp_token_issue_service import (
    MCPTokenIssueService,
    compute_lookup_key,
)
from app.application.services.mcp_token_revoke_service import (
    MCPTokenNotFoundError,
    MCPTokenRevokeService,
)
from app.application.services.mcp_token_rotate_service import MCPTokenRotateService
from app.domain.models.mcp_token import MCPToken
from tests.fakes.fake_mcp_token_repositories import (
    FakeCache,
    FakeMCPTokenRepository,
    FakeMembershipRepo,
)

_PEPPER = "test-pepper-32-chars-exactly-here"
_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()


def _make_service() -> tuple[MCPTokenRotateService, FakeMCPTokenRepository, FakeMembershipRepo]:
    repo = FakeMCPTokenRepository()
    membership_repo = FakeMembershipRepo()
    membership_repo.add_member(_WORKSPACE_ID, _USER_ID)
    cache = FakeCache()

    issue_svc = MCPTokenIssueService(token_repo=repo, membership_repo=membership_repo, pepper=_PEPPER)
    revoke_svc = MCPTokenRevokeService(token_repo=repo, cache=cache)
    rotate_svc = MCPTokenRotateService(
        token_repo=repo,
        revoke_service=revoke_svc,
        issue_service=issue_svc,
    )
    return rotate_svc, repo, membership_repo


@pytest.mark.asyncio
async def test_rotate_revokes_old_token() -> None:
    rotate_svc, repo, _ = _make_service()

    # Issue an original token
    old_token = MCPToken.create(
        workspace_id=_WORKSPACE_ID,
        user_id=_USER_ID,
        name="My Bot",
        token_hash_argon2="fake",
        lookup_key_hmac=compute_lookup_key("mcp_" + "a" * 43, _PEPPER),
        scopes=["mcp:read"],
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await repo.save(old_token)

    await rotate_svc.rotate(old_token.id, _WORKSPACE_ID)

    stored_old = repo._by_id[old_token.id]
    assert stored_old.is_revoked


@pytest.mark.asyncio
async def test_rotate_issues_new_token_with_same_name_and_workspace() -> None:
    rotate_svc, repo, _ = _make_service()

    old_token = MCPToken.create(
        workspace_id=_WORKSPACE_ID,
        user_id=_USER_ID,
        name="My Bot",
        token_hash_argon2="fake",
        lookup_key_hmac=compute_lookup_key("mcp_" + "b" * 43, _PEPPER),
        scopes=["mcp:read"],
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await repo.save(old_token)

    new_issued = await rotate_svc.rotate(old_token.id, _WORKSPACE_ID)

    assert new_issued.name == "My Bot"
    assert new_issued.plaintext.startswith("mcp_")


@pytest.mark.asyncio
async def test_rotate_records_rotated_from() -> None:
    rotate_svc, repo, _ = _make_service()

    old_token = MCPToken.create(
        workspace_id=_WORKSPACE_ID,
        user_id=_USER_ID,
        name="Rotating Bot",
        token_hash_argon2="fake",
        lookup_key_hmac=compute_lookup_key("mcp_" + "c" * 43, _PEPPER),
        scopes=[],
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    await repo.save(old_token)

    new_issued = await rotate_svc.rotate(old_token.id, _WORKSPACE_ID)

    # Find new token in repo
    new_token = next(t for t in repo._by_id.values() if t.id == new_issued.id)
    assert new_token.rotated_from == old_token.id


@pytest.mark.asyncio
async def test_rotate_raises_not_found_for_unknown_token() -> None:
    rotate_svc, _, _ = _make_service()

    with pytest.raises(MCPTokenNotFoundError):
        await rotate_svc.rotate(uuid4(), _WORKSPACE_ID)
