"""AuthService unit tests — orchestrates OAuth + sessions + audit.

All collaborators are fakes; no DB, no HTTP.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.auth_service import (
    AuthService,
    InvalidStateError,
    NoWorkspaceAccessError,
    SessionExpiredError,
    SessionRevokedError,
    UserSuspendedError,
)
from app.application.services.membership_resolver_service import (
    MembershipResolverService,
)
from app.application.services.superadmin_seed_service import SuperadminSeedService
from app.domain.models.session import Session
from app.domain.models.user import User
from app.domain.models.workspace_membership import WorkspaceMembership
from app.infrastructure.adapters.google_oauth_adapter import (
    GoogleClaims,
    OAuthExchangeError,
)
from app.infrastructure.adapters.jwt_adapter import JwtAdapter
from tests.fakes.fake_google_oauth import FakeGoogleOAuthAdapter
from tests.fakes.fake_repositories import (
    FakeAuditRepository,
    FakeOAuthStateRepository,
    FakeSessionRepository,
    FakeUserRepository,
    FakeWorkspaceMembershipRepository,
)


@pytest.fixture
def audit_repo() -> FakeAuditRepository:
    return FakeAuditRepository()


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def sessions() -> FakeSessionRepository:
    return FakeSessionRepository()


@pytest.fixture
def memberships() -> FakeWorkspaceMembershipRepository:
    return FakeWorkspaceMembershipRepository()


@pytest.fixture
def oauth_states() -> FakeOAuthStateRepository:
    return FakeOAuthStateRepository()


@pytest.fixture
def jwt_adapter() -> JwtAdapter:
    return JwtAdapter(
        secret="unit-test-secret-at-least-32-bytes-x", algorithm="HS256"
    )


@pytest.fixture
def google() -> FakeGoogleOAuthAdapter:
    return FakeGoogleOAuthAdapter(
        claims=GoogleClaims(
            sub="sub-alice",
            email="alice@tuio.com",
            name="Alice",
            picture="https://x/p.png",
        )
    )


@pytest.fixture
def service(
    users,
    sessions,
    memberships,
    oauth_states,
    audit_repo,
    jwt_adapter,
    google,
) -> AuthService:
    audit = AuditService(audit_repo)
    return AuthService(
        user_repo=users,
        session_repo=sessions,
        oauth_state_repo=oauth_states,
        google_oauth=google,
        jwt_adapter=jwt_adapter,
        audit_service=audit,
        superadmin_seed=SuperadminSeedService(
            user_repo=users, audit_service=audit, seeded_emails=["root@tuio.com"]
        ),
        membership_resolver=MembershipResolverService(memberships),
        access_token_ttl_seconds=900,
        refresh_token_ttl_seconds=2_592_000,
        oauth_state_ttl_seconds=300,
    )


# ---------------------------------------------------------------------------
# initiate_oauth
# ---------------------------------------------------------------------------


async def test_initiate_oauth_persists_state_and_returns_google_url(
    service, oauth_states
) -> None:
    result = await service.initiate_oauth()

    assert "state=" in result.authorization_url
    assert "code_challenge=" in result.authorization_url
    assert "code_challenge_method=S256" in result.authorization_url
    # State row lives in the repo; consume should return the verifier.
    consumed = await oauth_states.consume(result.state)
    assert consumed is not None and len(consumed.verifier) >= 32


# ---------------------------------------------------------------------------
# handle_callback — happy path + routing
# ---------------------------------------------------------------------------


async def test_callback_with_single_active_membership_succeeds(
    service, users, sessions, memberships, audit_repo
) -> None:
    init = await service.initiate_oauth()

    # Pre-seed: user already exists with one active membership
    existing = User.from_google_claims(
        sub="sub-alice", email="alice@tuio.com", name="Alice", picture=None
    )
    await users.upsert(existing)
    ws_id = uuid4()
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws_id, user_id=existing.id, role="member", is_default=True
        )
    )

    result = await service.handle_callback(
        code="auth-code", state=init.state, ip_address="10.0.0.1", user_agent="ua",
    )

    assert result.outcome.kind == "single"
    assert result.outcome.workspace_id == ws_id
    assert result.tokens is not None
    # Session persisted with the refresh token hash
    stored = await sessions.get_by_token_hash(
        Session.hash_token(result.tokens.refresh_token)
    )
    assert stored is not None and stored.user_id == existing.id
    # Audit event for login_success
    assert any(e.action == "login_success" for e in audit_repo.events)


async def test_callback_with_zero_active_memberships_raises_and_emits_block(
    service, users, audit_repo
) -> None:
    init = await service.initiate_oauth()

    # No membership created → 0 active
    with pytest.raises(NoWorkspaceAccessError):
        await service.handle_callback(
            code="c", state=init.state, ip_address=None, user_agent=None,
        )

    # audit event emitted
    assert any(
        e.action == "login_blocked_no_workspace" for e in audit_repo.events
    )
    # User row still created (Google claims present) so admin can grant access later
    assert await users.get_by_google_sub("sub-alice") is not None


async def test_callback_with_multiple_memberships_returns_picker(
    service, users, memberships
) -> None:
    init = await service.initiate_oauth()
    existing = User.from_google_claims(
        sub="sub-alice", email="alice@tuio.com", name="Alice", picture=None
    )
    await users.upsert(existing)
    ws1, ws2 = uuid4(), uuid4()
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws1, user_id=existing.id, role="member", is_default=True
        )
    )
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws2, user_id=existing.id, role="member", is_default=False
        )
    )

    result = await service.handle_callback(
        code="c", state=init.state, ip_address=None, user_agent=None,
    )
    assert result.outcome.kind == "picker"
    # tokens still issued — user is authenticated, just needs to pick a workspace
    assert result.tokens is not None


async def test_callback_respects_last_chosen_workspace(
    service, users, memberships
) -> None:
    """last_chosen_workspace_id is persisted in the state row, not passed at callback time."""
    existing = User.from_google_claims(
        sub="sub-alice", email="alice@tuio.com", name="Alice", picture=None
    )
    await users.upsert(existing)
    ws1, ws2 = uuid4(), uuid4()
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws1, user_id=existing.id, role="member", is_default=True
        )
    )
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws2, user_id=existing.id, role="member", is_default=False
        )
    )

    # ws2 is stored in the state row
    init = await service.initiate_oauth(last_chosen_workspace_id=ws2)

    result = await service.handle_callback(
        code="c",
        state=init.state,
        ip_address=None,
        user_agent=None,
    )
    assert result.outcome.kind == "single"
    assert result.outcome.workspace_id == ws2


# ---------------------------------------------------------------------------
# handle_callback — error paths
# ---------------------------------------------------------------------------


async def test_callback_with_unknown_state_raises_invalid_state(service) -> None:
    with pytest.raises(InvalidStateError):
        await service.handle_callback(
            code="c", state="nonexistent", ip_address=None, user_agent=None,
        )


async def test_callback_consumes_state_once(service, oauth_states) -> None:
    init = await service.initiate_oauth()
    # First callback fails (no membership) but must still consume the state.
    with pytest.raises(NoWorkspaceAccessError):
        await service.handle_callback(
            code="c", state=init.state, ip_address=None, user_agent=None,
        )
    # Replay must fail as invalid state, not NoWorkspaceAccessError.
    with pytest.raises(InvalidStateError):
        await service.handle_callback(
            code="c", state=init.state, ip_address=None, user_agent=None,
        )


async def test_callback_when_google_fails_preserves_audit(
    service, users, memberships, audit_repo, google
) -> None:
    init = await service.initiate_oauth()
    google._raise = OAuthExchangeError("boom")

    with pytest.raises(OAuthExchangeError):
        await service.handle_callback(
            code="c", state=init.state, ip_address="10.0.0.1", user_agent=None,
        )

    assert any(
        e.action == "login_failed_oauth_exchange" for e in audit_repo.events
    )
    # No user row touched
    assert await users.get_by_google_sub("sub-alice") is None


# ---------------------------------------------------------------------------
# handle_callback — superadmin seed
# ---------------------------------------------------------------------------


async def test_seeded_email_becomes_superadmin_on_first_login(
    service, users, memberships, google, audit_repo
) -> None:
    init = await service.initiate_oauth()
    google._claims = GoogleClaims(
        sub="sub-root", email="root@tuio.com", name="Root", picture=None
    )
    # Give root at least one active membership so the flow completes
    # (membership must exist before login since seed happens in-flow)
    # Here we let the membership be added post-upsert manually for test clarity.

    # We'll work around by inserting membership after Google call but before resolver
    # — not straightforward here. Instead, assert superadmin flag even with no_access.
    with pytest.raises(NoWorkspaceAccessError):
        await service.handle_callback(
            code="c", state=init.state, ip_address=None, user_agent=None,
        )

    stored = await users.get_by_email("root@tuio.com")
    assert stored is not None
    assert stored.is_superadmin is True
    assert any(e.action == "superadmin_seeded" for e in audit_repo.events)


# ---------------------------------------------------------------------------
# refresh_token
# ---------------------------------------------------------------------------


async def test_refresh_token_happy_path(
    service, users, sessions, memberships
) -> None:
    # Set up existing login session
    user = User.from_google_claims(
        sub="s-r", email="r@tuio.com", name="R", picture=None
    )
    await users.upsert(user)
    ws_id = uuid4()
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws_id, user_id=user.id, role="member", is_default=True
        )
    )
    raw = "raw-refresh-xyz"
    await sessions.create(
        Session.create(
            user_id=user.id, raw_token=raw, ttl_seconds=3600,
            ip_address=None, user_agent=None,
        )
    )

    pair = await service.refresh_token(raw_refresh_token=raw, workspace_id=ws_id)
    assert pair.access_token
    claims = service.decode_access_token(pair.access_token)
    assert claims["sub"] == str(user.id)
    assert claims["workspace_id"] == str(ws_id)


async def test_refresh_token_expired_raises(service, users, sessions) -> None:
    user = User.from_google_claims(
        sub="s-e", email="e@tuio.com", name="E", picture=None
    )
    await users.upsert(user)
    raw = "raw-exp"
    session = Session.create(
        user_id=user.id, raw_token=raw, ttl_seconds=3600,
        ip_address=None, user_agent=None,
    )
    session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    await sessions.create(session)

    with pytest.raises(SessionExpiredError):
        await service.refresh_token(raw_refresh_token=raw, workspace_id=None)


async def test_refresh_token_revoked_raises(service, users, sessions) -> None:
    user = User.from_google_claims(
        sub="s-rev", email="rv@tuio.com", name="Rv", picture=None
    )
    await users.upsert(user)
    raw = "raw-rev"
    session = Session.create(
        user_id=user.id, raw_token=raw, ttl_seconds=3600,
        ip_address=None, user_agent=None,
    )
    await sessions.create(session)
    await sessions.revoke(session.id)

    with pytest.raises(SessionRevokedError):
        await service.refresh_token(raw_refresh_token=raw, workspace_id=None)


async def test_refresh_token_unknown_raises(service) -> None:
    with pytest.raises(InvalidStateError):
        await service.refresh_token(raw_refresh_token="nope", workspace_id=None)


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


async def test_logout_revokes_session_and_audits(
    service, users, sessions, audit_repo
) -> None:
    user = User.from_google_claims(
        sub="s-l", email="l@tuio.com", name="L", picture=None
    )
    await users.upsert(user)
    raw = "raw-logout"
    session = Session.create(
        user_id=user.id, raw_token=raw, ttl_seconds=3600,
        ip_address=None, user_agent=None,
    )
    await sessions.create(session)

    await service.logout(raw_refresh_token=raw, actor_id=user.id)

    stored = await sessions.get_by_token_hash(Session.hash_token(raw))
    assert stored is not None
    assert stored.is_revoked() is True
    assert any(e.action == "logout" for e in audit_repo.events)


async def test_logout_unknown_session_is_noop(service, audit_repo) -> None:
    await service.logout(raw_refresh_token="never-seen", actor_id=None)
    assert not any(e.action == "logout" for e in audit_repo.events)


# ---------------------------------------------------------------------------
# refresh_token — IDOR guard + suspended user (fixes EP-00 hardening)
# ---------------------------------------------------------------------------


async def test_refresh_token_idor_rejects_non_member_workspace(
    service, users, sessions, memberships
) -> None:
    """User A must not be able to mint a token for a workspace they don't belong to."""
    user = User.from_google_claims(
        sub="s-idor", email="idor@tuio.com", name="IDOR", picture=None
    )
    await users.upsert(user)
    ws_owned = uuid4()
    ws_foreign = uuid4()
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws_owned, user_id=user.id, role="member", is_default=True
        )
    )
    raw = "raw-idor"
    await sessions.create(
        Session.create(
            user_id=user.id, raw_token=raw, ttl_seconds=3600,
            ip_address=None, user_agent=None,
        )
    )

    with pytest.raises(NoWorkspaceAccessError):
        await service.refresh_token(raw_refresh_token=raw, workspace_id=ws_foreign)


async def test_refresh_token_suspended_user_raises(
    service, users, sessions
) -> None:
    user = User.from_google_claims(
        sub="s-sus", email="sus@tuio.com", name="Sus", picture=None
    )
    await users.upsert(user)
    user.status = "suspended"  # mutate after upsert to simulate admin action

    raw = "raw-sus"
    await sessions.create(
        Session.create(
            user_id=user.id, raw_token=raw, ttl_seconds=3600,
            ip_address=None, user_agent=None,
        )
    )

    with pytest.raises(UserSuspendedError):
        await service.refresh_token(raw_refresh_token=raw, workspace_id=None)


async def test_refresh_token_deleted_user_raises(
    service, users, sessions
) -> None:
    user = User.from_google_claims(
        sub="s-del", email="del@tuio.com", name="Del", picture=None
    )
    await users.upsert(user)
    user.status = "deleted"

    raw = "raw-del"
    await sessions.create(
        Session.create(
            user_id=user.id, raw_token=raw, ttl_seconds=3600,
            ip_address=None, user_agent=None,
        )
    )

    with pytest.raises(UserSuspendedError):
        await service.refresh_token(raw_refresh_token=raw, workspace_id=None)


# ---------------------------------------------------------------------------
# OAuth round-trip: return_to + last_chosen_workspace_id persisted via state row
# ---------------------------------------------------------------------------


async def test_initiate_oauth_persists_return_to_and_last_workspace(
    service, oauth_states, users, memberships
) -> None:
    ws_id = uuid4()
    result = await service.initiate_oauth(
        return_to="/workspace/foo",
        last_chosen_workspace_id=ws_id,
    )
    consumed = await oauth_states.consume(result.state)
    assert consumed is not None
    assert consumed.return_to == "/workspace/foo"
    assert consumed.last_chosen_workspace_id == ws_id


async def test_handle_callback_returns_return_to_from_state_row(
    service, users, memberships, oauth_states
) -> None:
    ws_id = uuid4()
    init = await service.initiate_oauth(
        return_to="/workspace/bar",
        last_chosen_workspace_id=None,
    )

    existing = User.from_google_claims(
        sub="sub-alice", email="alice@tuio.com", name="Alice", picture=None
    )
    await users.upsert(existing)
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws_id, user_id=existing.id, role="member", is_default=True
        )
    )

    result = await service.handle_callback(
        code="c", state=init.state, ip_address=None, user_agent=None
    )
    assert result.return_to == "/workspace/bar"


async def test_handle_callback_ignores_client_supplied_last_workspace_in_callback(
    service, users, memberships, oauth_states
) -> None:
    """last_chosen_workspace_id comes from the state row, not the callback call site."""
    ws1 = uuid4()
    ws2 = uuid4()
    # initiate with ws1 stored
    init = await service.initiate_oauth(
        return_to=None,
        last_chosen_workspace_id=ws1,
    )

    existing = User.from_google_claims(
        sub="sub-alice", email="alice@tuio.com", name="Alice", picture=None
    )
    await users.upsert(existing)
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws1, user_id=existing.id, role="member", is_default=False
        )
    )
    await memberships.create(
        WorkspaceMembership.create(
            workspace_id=ws2, user_id=existing.id, role="member", is_default=True
        )
    )

    # handle_callback no longer accepts last_chosen_workspace_id from caller
    result = await service.handle_callback(
        code="c", state=init.state, ip_address=None, user_agent=None
    )
    # ws1 was stored in the state row → should be used
    assert result.outcome.workspace_id == ws1
