"""Unit tests for MCPTokenRevokeService — EP-18 Capability 1."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.mcp_token_issue_service import compute_lookup_key, hash_token_argon2
from app.application.services.mcp_token_revoke_service import (
    MCPTokenNotFoundError,
    MCPTokenRevokeService,
)
from app.domain.models.mcp_token import MCPToken
from tests.fakes.fake_mcp_token_repositories import FakeCache, FakeMCPTokenRepository

_PEPPER = "test-pepper-32-chars-exactly-here"
_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()


def _make_token(plaintext: str = "mcp_" + "a" * 43) -> MCPToken:
    return MCPToken.create(
        workspace_id=_WORKSPACE_ID,
        user_id=_USER_ID,
        name="Test",
        token_hash_argon2="fake",
        lookup_key_hmac=compute_lookup_key(plaintext, _PEPPER),
        scopes=[],
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at() -> None:
    repo = FakeMCPTokenRepository()
    token = _make_token()
    await repo.save(token)

    svc = MCPTokenRevokeService(token_repo=repo)
    await svc.revoke(token.id, _WORKSPACE_ID)

    stored = repo._by_id[token.id]
    assert stored.revoked_at is not None


@pytest.mark.asyncio
async def test_revoke_is_idempotent() -> None:
    repo = FakeMCPTokenRepository()
    token = _make_token()
    await repo.save(token)

    svc = MCPTokenRevokeService(token_repo=repo)
    await svc.revoke(token.id, _WORKSPACE_ID)
    first_revoked_at = repo._by_id[token.id].revoked_at

    # Second call — should not change revoked_at
    await svc.revoke(token.id, _WORKSPACE_ID)
    second_revoked_at = repo._by_id[token.id].revoked_at

    assert first_revoked_at == second_revoked_at


@pytest.mark.asyncio
async def test_revoke_raises_not_found_for_unknown_token() -> None:
    repo = FakeMCPTokenRepository()
    svc = MCPTokenRevokeService(token_repo=repo)

    with pytest.raises(MCPTokenNotFoundError):
        await svc.revoke(uuid4(), _WORKSPACE_ID)


@pytest.mark.asyncio
async def test_revoke_raises_not_found_for_wrong_workspace() -> None:
    repo = FakeMCPTokenRepository()
    token = _make_token()
    await repo.save(token)

    svc = MCPTokenRevokeService(token_repo=repo)

    with pytest.raises(MCPTokenNotFoundError):
        await svc.revoke(token.id, uuid4())  # different workspace


@pytest.mark.asyncio
async def test_revoke_deletes_cache_key() -> None:
    repo = FakeMCPTokenRepository()
    cache = FakeCache()
    token = _make_token()
    await repo.save(token)

    # Pre-populate cache
    cache_key = f"mcp:token:{token.lookup_key_hmac.hex()}"
    await cache.set(cache_key, {"workspace_id": str(_WORKSPACE_ID), "user_id": str(_USER_ID), "scopes": [], "token_id": str(token.id)})

    svc = MCPTokenRevokeService(token_repo=repo, cache=cache)
    await svc.revoke(token.id, _WORKSPACE_ID)

    assert await cache.get(cache_key) is None
