"""SuperadminSeedService unit tests."""

from __future__ import annotations

import pytest

from app.application.services.audit_service import AuditService
from app.application.services.superadmin_seed_service import SuperadminSeedService
from app.domain.models.user import User
from tests.fakes.fake_repositories import FakeAuditRepository, FakeUserRepository


@pytest.fixture
def users() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def audit() -> FakeAuditRepository:
    return FakeAuditRepository()


def _user(email: str) -> User:
    return User.from_google_claims(sub=f"sub-{email}", email=email, name="N", picture=None)


async def test_seeded_email_flips_is_superadmin(users, audit) -> None:
    service = SuperadminSeedService(
        user_repo=users,
        audit_service=AuditService(audit),
        seeded_emails=["ceo@tuio.com", "cto@tuio.com"],
    )
    user = _user("ceo@tuio.com")
    await users.upsert(user)

    await service.on_user_created(user)

    assert user.is_superadmin is True
    stored = await users.get_by_email("ceo@tuio.com")
    assert stored and stored.is_superadmin is True
    assert any(e.action == "superadmin_seeded" for e in audit.events)


async def test_non_seeded_email_unchanged(users, audit) -> None:
    service = SuperadminSeedService(
        user_repo=users,
        audit_service=AuditService(audit),
        seeded_emails=["ceo@tuio.com"],
    )
    user = _user("intern@tuio.com")
    await users.upsert(user)

    await service.on_user_created(user)

    assert user.is_superadmin is False
    assert not any(e.action == "superadmin_seeded" for e in audit.events)


async def test_seed_list_is_case_insensitive(users, audit) -> None:
    service = SuperadminSeedService(
        user_repo=users,
        audit_service=AuditService(audit),
        seeded_emails=["CEO@TUIO.com"],
    )
    user = _user("ceo@tuio.com")  # normalized lowercase at domain boundary
    await users.upsert(user)

    await service.on_user_created(user)

    assert user.is_superadmin is True


async def test_already_superadmin_is_noop(users, audit) -> None:
    service = SuperadminSeedService(
        user_repo=users,
        audit_service=AuditService(audit),
        seeded_emails=["ceo@tuio.com"],
    )
    user = _user("ceo@tuio.com")
    user.is_superadmin = True
    await users.upsert(user)

    await service.on_user_created(user)

    # No second audit event — idempotent.
    assert sum(1 for e in audit.events if e.action == "superadmin_seeded") == 0


async def test_empty_seed_list_is_noop(users, audit) -> None:
    service = SuperadminSeedService(
        user_repo=users,
        audit_service=AuditService(audit),
        seeded_emails=[],
    )
    user = _user("ceo@tuio.com")
    await users.upsert(user)

    await service.on_user_created(user)

    assert user.is_superadmin is False
