"""UserRepositoryImpl integration tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.user import User
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl


@pytest.fixture
def repo(db_session) -> UserRepositoryImpl:
    return UserRepositoryImpl(db_session)


async def test_upsert_inserts_new_user(repo, db_session) -> None:
    user = User.from_google_claims(sub="sub-1", email="alice@tuio.com", name="Alice", picture=None)
    saved = await repo.upsert(user)
    await db_session.commit()

    assert saved.id == user.id
    fetched = await repo.get_by_google_sub("sub-1")
    assert fetched is not None
    assert fetched.email == "alice@tuio.com"
    assert fetched.is_superadmin is False


async def test_upsert_updates_existing_user_by_google_sub(repo, db_session) -> None:
    original = User.from_google_claims(sub="sub-2", email="bob@tuio.com", name="Bob", picture=None)
    await repo.upsert(original)
    await db_session.commit()

    # Same `google_sub`, different email and name → update, same id
    updated = User.from_google_claims(
        sub="sub-2",
        email="bob-new@tuio.com",
        name="Bob New",
        picture="https://x/p.png",
    )
    # Override id to mimic resolving existing user before upsert
    updated.id = original.id
    saved = await repo.upsert(updated)
    await db_session.commit()

    assert saved.id == original.id
    fetched = await repo.get_by_google_sub("sub-2")
    assert fetched is not None
    assert fetched.id == original.id
    assert fetched.email == "bob-new@tuio.com"
    assert fetched.full_name == "Bob New"
    assert fetched.avatar_url == "https://x/p.png"


async def test_get_by_id_returns_none_for_missing(repo) -> None:
    assert await repo.get_by_id(uuid4()) is None


async def test_get_by_email_is_case_insensitive_at_domain_boundary(repo, db_session) -> None:
    user = User.from_google_claims(
        sub="sub-3", email="Charlie@Tuio.com", name="Charlie", picture=None
    )
    assert user.email == "charlie@tuio.com"  # normalized by User
    await repo.upsert(user)
    await db_session.commit()

    fetched = await repo.get_by_email("charlie@tuio.com")
    assert fetched is not None
    assert fetched.full_name == "Charlie"


async def test_upsert_roundtrips_is_superadmin_flag(repo, db_session) -> None:
    user = User.from_google_claims(
        sub="sub-super", email="super@tuio.com", name="Super", picture=None
    )
    user.is_superadmin = True
    await repo.upsert(user)
    await db_session.commit()

    fetched = await repo.get_by_email("super@tuio.com")
    assert fetched is not None
    assert fetched.is_superadmin is True
