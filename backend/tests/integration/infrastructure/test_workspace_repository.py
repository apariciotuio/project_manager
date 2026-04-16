"""WorkspaceRepositoryImpl integration tests."""

from __future__ import annotations

import pytest

from app.domain.models.user import User
from app.domain.models.workspace import Workspace
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl
from app.infrastructure.persistence.workspace_repository_impl import WorkspaceRepositoryImpl


@pytest.fixture
def repo(db_session) -> WorkspaceRepositoryImpl:
    return WorkspaceRepositoryImpl(db_session)


@pytest.fixture
def users(db_session) -> UserRepositoryImpl:
    return UserRepositoryImpl(db_session)


async def _persisted_user(users, db_session, *, sub: str, email: str) -> User:
    user = User.from_google_claims(sub=sub, email=email, name="N", picture=None)
    await users.upsert(user)
    await db_session.commit()
    return user


async def test_create_and_get_by_slug(repo, users, db_session) -> None:
    creator = await _persisted_user(users, db_session, sub="s", email="a@acme.io")
    ws = Workspace.create_from_email(email="a@acme.io", created_by=creator.id)
    saved = await repo.create(ws)
    await db_session.commit()

    fetched = await repo.get_by_slug("acme")
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.name == "Acme"


async def test_get_by_slug_miss(repo) -> None:
    assert await repo.get_by_slug("nope") is None


async def test_slug_exists_reports_correctly(repo, users, db_session) -> None:
    creator = await _persisted_user(users, db_session, sub="s2", email="a@tuio.com")
    ws = Workspace.create_from_email(email="a@tuio.com", created_by=creator.id)
    await repo.create(ws)
    await db_session.commit()

    assert await repo.slug_exists("tuio") is True
    assert await repo.slug_exists("nonexistent") is False


async def test_duplicate_slug_raises(repo, users, db_session) -> None:
    from app.infrastructure.persistence.workspace_repository_impl import WorkspaceSlugConflictError

    creator = await _persisted_user(users, db_session, sub="s3", email="a@acme.io")
    first = Workspace.create_from_email(email="a@acme.io", created_by=creator.id)
    await repo.create(first)
    await db_session.commit()

    dup = Workspace.create_from_email(email="b@acme.io", created_by=creator.id)
    # Same slug "acme" — unique constraint must raise WorkspaceSlugConflictError.
    with pytest.raises(WorkspaceSlugConflictError):
        await repo.create(dup)
        await db_session.commit()
