"""Unit tests for MCPTokenIssueService — EP-18 Capability 1.

RED → GREEN → REFACTOR cycle.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.application.services.mcp_token_issue_service import (
    _TOKEN_REGEX,
    MCPTokenIssueService,
    MCPTokenLimitError,
    MCPTokenNotMemberError,
    MCPTokenTTLError,
    generate_token_plaintext,
)
from tests.fakes.fake_mcp_token_repositories import (
    FakeMCPTokenRepository,
    FakeMembershipRepo,
)

_PEPPER = "test-pepper-32-chars-exactly-here"
_WORKSPACE_ID = uuid4()
_USER_ID = uuid4()


def _make_service(
    *,
    is_member: bool = True,
    existing_active_count: int = 0,
) -> MCPTokenIssueService:
    repo = FakeMCPTokenRepository()
    membership_repo = FakeMembershipRepo()
    if is_member:
        membership_repo.add_member(_WORKSPACE_ID, _USER_ID)
    return MCPTokenIssueService(
        token_repo=repo,
        membership_repo=membership_repo,
        pepper=_PEPPER,
    )


@pytest.mark.asyncio
async def test_issue_happy_path_returns_plaintext_id_and_expires_at() -> None:
    svc = _make_service()

    result = await svc.issue(
        workspace_id=_WORKSPACE_ID,
        target_user_id=_USER_ID,
        name="CI Bot",
    )

    assert result.plaintext.startswith("mcp_")
    assert result.id is not None
    assert result.expires_at > datetime.now(UTC)
    assert result.name == "CI Bot"


@pytest.mark.asyncio
async def test_issue_rejects_when_not_member_of_workspace() -> None:
    svc = _make_service(is_member=False)

    with pytest.raises(MCPTokenNotMemberError):
        await svc.issue(
            workspace_id=_WORKSPACE_ID,
            target_user_id=_USER_ID,
            name="Bot",
        )


@pytest.mark.asyncio
async def test_issue_rejects_when_user_already_at_10_tokens() -> None:
    repo = FakeMCPTokenRepository()
    membership_repo = FakeMembershipRepo()
    membership_repo.add_member(_WORKSPACE_ID, _USER_ID)
    svc = MCPTokenIssueService(token_repo=repo, membership_repo=membership_repo, pepper=_PEPPER)

    # Pre-fill 10 active tokens
    import hashlib
    import hmac as _hmac

    from app.domain.models.mcp_token import MCPToken

    for i in range(10):
        plaintext = f"mcp_{'x' * 43}"
        lookup = _hmac.new(_PEPPER.encode(), f"tok{i}".encode(), hashlib.sha256).digest()
        token = MCPToken.create(
            workspace_id=_WORKSPACE_ID,
            user_id=_USER_ID,
            name=f"token-{i}",
            token_hash_argon2="fake-hash",
            lookup_key_hmac=lookup,
            scopes=[],
            expires_at=datetime.now(UTC) + timedelta(days=30),
        )
        await repo.save(token)

    with pytest.raises(MCPTokenLimitError):
        await svc.issue(
            workspace_id=_WORKSPACE_ID,
            target_user_id=_USER_ID,
            name="Over Limit",
        )


@pytest.mark.asyncio
async def test_issue_rejects_expires_over_90_days() -> None:
    svc = _make_service()

    with pytest.raises(MCPTokenTTLError):
        await svc.issue(
            workspace_id=_WORKSPACE_ID,
            target_user_id=_USER_ID,
            name="LongLived",
            expires_in_days=91,
        )


@pytest.mark.asyncio
async def test_issue_at_exactly_90_days_succeeds() -> None:
    svc = _make_service()
    result = await svc.issue(
        workspace_id=_WORKSPACE_ID,
        target_user_id=_USER_ID,
        name="MaxTTL",
        expires_in_days=90,
    )
    delta = result.expires_at - datetime.now(UTC)
    assert delta.days >= 89  # within ~1s tolerance


@pytest.mark.asyncio
async def test_issue_plaintext_format_matches_regex() -> None:
    svc = _make_service()
    # Multiple samples — triangulation
    for _ in range(5):
        result = await svc.issue(
            workspace_id=_WORKSPACE_ID,
            target_user_id=_USER_ID,
            name="Format Check",
        )
        assert _TOKEN_REGEX.match(result.plaintext), (
            f"Token {result.plaintext!r} does not match regex"
        )


def test_generate_token_plaintext_format() -> None:
    for _ in range(10):
        token = generate_token_plaintext()
        assert _TOKEN_REGEX.match(token), f"{token!r} does not match regex"


@pytest.mark.asyncio
async def test_issue_stores_lookup_key_not_plaintext_in_db() -> None:
    repo = FakeMCPTokenRepository()
    membership_repo = FakeMembershipRepo()
    membership_repo.add_member(_WORKSPACE_ID, _USER_ID)
    svc = MCPTokenIssueService(token_repo=repo, membership_repo=membership_repo, pepper=_PEPPER)

    result = await svc.issue(
        workspace_id=_WORKSPACE_ID,
        target_user_id=_USER_ID,
        name="Storage Check",
    )

    # Lookup by ID — token in repo must NOT contain plaintext
    stored = next(t for t in repo._by_id.values() if t.id == result.id)
    assert result.plaintext not in stored.token_hash_argon2
    assert result.plaintext.encode() not in stored.lookup_key_hmac
