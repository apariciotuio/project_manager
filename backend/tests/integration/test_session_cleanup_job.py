"""EP-00 Phase 9 — cleanup_expired_sessions integration.

Runs the async function against the real testcontainer DB. Asserts expired rows
are removed, active rows untouched, the return count matches, and the empty
case returns 0.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.models.session import Session
from app.domain.models.user import User
from app.infrastructure.persistence.models.orm import SessionORM
from app.infrastructure.persistence.session_repository_impl import SessionRepositoryImpl
from app.infrastructure.persistence.user_repository_impl import UserRepositoryImpl


@pytest_asyncio.fixture
async def clean_db(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE workspace_memberships, sessions, oauth_states, "
                "workspaces, users RESTART IDENTITY CASCADE"
            )
        )
    yield engine
    await engine.dispose()

    db_module._engine = None
    db_module._session_factory = None


async def _seed_user(engine) -> User:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        repo = UserRepositoryImpl(s)
        user = User.from_google_claims(
            sub=f"sub-{uuid4()}", email=f"{uuid4()}@tuio.com", name="U", picture=None
        )
        saved = await repo.upsert(user)
        await s.commit()
    return saved


async def _seed_session(engine, *, user_id, expires_at, revoked_at=None) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        repo = SessionRepositoryImpl(s)
        await repo.create(
            Session(
                id=uuid4(),
                user_id=user_id,
                token_hash=f"h-{uuid4()}",
                expires_at=expires_at,
                revoked_at=revoked_at,
                ip_address=None,
                user_agent=None,
                created_at=datetime.now(timezone.utc),
            )
        )
        await s.commit()


async def _count_sessions(engine) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        rows = (await s.execute(select(SessionORM))).scalars().all()
        return len(rows)


async def test_cleanup_deletes_only_expired_sessions(clean_db) -> None:
    user = await _seed_user(clean_db)
    now = datetime.now(timezone.utc)
    # 2 expired, 3 active
    for _ in range(2):
        await _seed_session(clean_db, user_id=user.id, expires_at=now - timedelta(hours=1))
    for _ in range(3):
        await _seed_session(clean_db, user_id=user.id, expires_at=now + timedelta(hours=1))

    from app.infrastructure.jobs.session_cleanup import cleanup_expired_sessions

    deleted = await cleanup_expired_sessions()
    assert deleted == 2
    assert await _count_sessions(clean_db) == 3


async def test_cleanup_returns_zero_on_empty_table(clean_db) -> None:
    from app.infrastructure.jobs.session_cleanup import cleanup_expired_sessions

    assert await cleanup_expired_sessions() == 0
