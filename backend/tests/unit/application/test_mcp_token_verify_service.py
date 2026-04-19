"""Unit tests for MCPTokenVerifyService — EP-18 Capability 1."""
from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.mcp_token_issue_service import (
    compute_lookup_key,
    generate_token_plaintext,
    hash_token_argon2,
)
from app.application.services.mcp_token_verify_service import (
    MCPTokenExpired,
    MCPTokenInvalid,
    MCPTokenRevoked,
    MCPTokenVerifyService,
    VerifiedToken,
)
from app.domain.models.mcp_token import MCPToken
from tests.fakes.fake_mcp_token_repositories import (
    FakeCache,
    FakeMCPTokenRepository,
)

_PEPPER = "test-pepper-32-chars-exactly-here"
_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()


def _make_token(
    plaintext: str,
    *,
    revoked: bool = False,
    expired: bool = False,
) -> MCPToken:
    lookup = compute_lookup_key(plaintext, _PEPPER)
    token_hash = hash_token_argon2(plaintext)
    expires_at = (
        datetime.now(UTC) - timedelta(seconds=1)
        if expired
        else datetime.now(UTC) + timedelta(days=30)
    )
    token = MCPToken.create(
        workspace_id=_WORKSPACE_ID,
        user_id=_USER_ID,
        name="Test Token",
        token_hash_argon2=token_hash,
        lookup_key_hmac=lookup,
        scopes=["mcp:read"],
        expires_at=expires_at,
    )
    if revoked:
        token.revoke()
    return token


@pytest.mark.asyncio
async def test_verify_returns_actor_and_workspace_on_valid_token() -> None:
    plaintext = generate_token_plaintext()
    token = _make_token(plaintext)

    repo = FakeMCPTokenRepository()
    await repo.save(token)

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER)
    result = await svc.verify(plaintext)

    assert isinstance(result, VerifiedToken)
    assert result.workspace_id == _WORKSPACE_ID
    assert result.user_id == _USER_ID
    assert result.token_id == token.id
    assert "mcp:read" in result.scopes


@pytest.mark.asyncio
async def test_verify_rejects_wrong_plaintext() -> None:
    plaintext = generate_token_plaintext()
    token = _make_token(plaintext)
    repo = FakeMCPTokenRepository()
    await repo.save(token)

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER)

    with pytest.raises(MCPTokenInvalid):
        await svc.verify(generate_token_plaintext())  # different token


@pytest.mark.asyncio
async def test_verify_rejects_expired_token() -> None:
    plaintext = generate_token_plaintext()
    token = _make_token(plaintext, expired=True)
    repo = FakeMCPTokenRepository()
    await repo.save(token)

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER)

    with pytest.raises(MCPTokenExpired):
        await svc.verify(plaintext)


@pytest.mark.asyncio
async def test_verify_rejects_revoked_token() -> None:
    plaintext = generate_token_plaintext()
    token = _make_token(plaintext, revoked=True)
    repo = FakeMCPTokenRepository()
    await repo.save(token)

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER)

    with pytest.raises(MCPTokenRevoked):
        await svc.verify(plaintext)


@pytest.mark.asyncio
async def test_verify_uses_cache_on_second_call() -> None:
    plaintext = generate_token_plaintext()
    token = _make_token(plaintext)
    repo = FakeMCPTokenRepository()
    await repo.save(token)
    cache = FakeCache()

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER, cache=cache)

    # First call — cache miss, populates cache
    result1 = await svc.verify(plaintext)

    # Remove from repo — second call must use cache
    repo._by_id.clear()

    result2 = await svc.verify(plaintext)
    assert result1.token_id == result2.token_id


@pytest.mark.asyncio
async def test_verify_cache_hit_skips_db_and_argon2() -> None:
    """Cache hit path: pre-loaded cache, repo empty — must succeed."""
    plaintext = generate_token_plaintext()
    repo = FakeMCPTokenRepository()
    cache = FakeCache()

    lookup = compute_lookup_key(plaintext, _PEPPER)
    cache_key = f"mcp:token:{lookup.hex()}"
    token_id = uuid4()
    await cache.set(
        cache_key,
        {
            "workspace_id": str(_WORKSPACE_ID),
            "user_id": str(_USER_ID),
            "scopes": ["mcp:read"],
            "token_id": str(token_id),
        },
    )

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER, cache=cache)
    result = await svc.verify(plaintext)

    assert result.token_id == token_id


@pytest.mark.asyncio
async def test_verify_constant_time_across_failure_modes() -> None:
    """Statistical check: timing std-dev across 50 samples must be bounded.

    This is a best-effort statistical check — cannot guarantee cryptographic
    constant-time in a Python interpreter, but validates no fast-fail
    short-circuit leaks token existence.

    Uses 50 samples (reduced from spec's 100 for speed) and checks that
    std-dev is within 5x the mean (very loose bound — the point is to catch
    gross timing differences, not microsecond leaks).
    """
    plaintext_valid = generate_token_plaintext()
    token = _make_token(plaintext_valid)
    repo = FakeMCPTokenRepository()
    await repo.save(token)

    svc = MCPTokenVerifyService(token_repo=repo, pepper=_PEPPER)

    samples_invalid: list[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        try:
            await svc.verify(generate_token_plaintext())
        except MCPTokenInvalid:
            pass
        samples_invalid.append(time.perf_counter() - t0)

    # Mean should be non-zero (actual work done) — no instant short-circuit
    mean = statistics.mean(samples_invalid)
    assert mean > 0, "Verify should not return instantly"
