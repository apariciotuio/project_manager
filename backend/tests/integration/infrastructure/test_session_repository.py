"""SessionRepositoryImpl integration tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.domain.models.session import Session
from app.domain.models.user import User
from app.infrastructure.persistence.session_repository_impl import SessionRepositoryImpl
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl


@pytest.fixture
def sessions(db_session) -> SessionRepositoryImpl:
    return SessionRepositoryImpl(db_session)


@pytest.fixture
def users(db_session) -> UserRepositoryImpl:
    return UserRepositoryImpl(db_session)


async def _persisted_user(users, db_session, *, sub: str, email: str) -> UUID:
    user = User.from_google_claims(sub=sub, email=email, name="N", picture=None)
    await users.upsert(user)
    await db_session.commit()
    return user.id


async def test_create_persists_session(sessions, users, db_session) -> None:
    user_id = await _persisted_user(users, db_session, sub="s-1", email="a@tuio.com")
    session = Session.create(
        user_id=user_id, raw_token="tok1", ttl_seconds=60,
        ip_address="10.0.0.1", user_agent="ua",
    )
    await sessions.create(session)
    await db_session.commit()

    fetched = await sessions.get_by_token_hash(Session.hash_token("tok1"))
    assert fetched is not None
    assert fetched.user_id == user_id
    assert fetched.is_active() is True
    assert fetched.ip_address == "10.0.0.1"


async def test_get_by_token_hash_misses(sessions) -> None:
    assert await sessions.get_by_token_hash("0" * 64) is None


async def test_revoke_sets_timestamp(sessions, users, db_session) -> None:
    from sqlalchemy import select

    from app.infrastructure.persistence.models.orm import SessionORM

    user_id = await _persisted_user(users, db_session, sub="s-2", email="b@tuio.com")
    session = Session.create(
        user_id=user_id, raw_token="tok2", ttl_seconds=60,
        ip_address=None, user_agent=None,
    )
    await sessions.create(session)
    await db_session.commit()

    await sessions.revoke(session.id)
    await db_session.commit()

    # get_by_token_hash filters revoked sessions — use raw ORM query to assert
    row = (
        await db_session.execute(
            select(SessionORM).where(SessionORM.id == session.id)
        )
    ).scalar_one_or_none()
    assert row is not None
    assert row.revoked_at is not None, "revoke must set revoked_at"

    # And the public API returns None for revoked sessions
    fetched = await sessions.get_by_token_hash(Session.hash_token("tok2"))
    assert fetched is None, "get_by_token_hash must filter revoked sessions"


async def test_delete_expired_removes_only_expired(sessions, users, db_session) -> None:
    user_id = await _persisted_user(users, db_session, sub="s-3", email="c@tuio.com")
    fresh = Session.create(
        user_id=user_id, raw_token="fresh", ttl_seconds=3600,
        ip_address=None, user_agent=None,
    )
    expired = Session.create(
        user_id=user_id, raw_token="expired", ttl_seconds=3600,
        ip_address=None, user_agent=None,
    )
    expired.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await sessions.create(fresh)
    await sessions.create(expired)
    await db_session.commit()

    deleted = await sessions.delete_expired()
    await db_session.commit()
    assert deleted == 1

    assert await sessions.get_by_token_hash(Session.hash_token("fresh")) is not None
    assert await sessions.get_by_token_hash(Session.hash_token("expired")) is None


async def test_revoke_unknown_id_is_noop(sessions, db_session) -> None:
    await sessions.revoke(uuid4())
    await db_session.commit()  # must not raise
