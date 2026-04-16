"""EP-00 Phase 9 — cleanup_expired_oauth_states integration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.infrastructure.persistence.models.orm import OAuthStateORM


@pytest_asyncio.fixture
async def clean_db(migrated_database):
    import app.infrastructure.persistence.database as db_module

    db_module._engine = None
    db_module._session_factory = None

    engine = create_async_engine(migrated_database.database.url)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE TABLE oauth_states RESTART IDENTITY CASCADE"))
    yield engine
    await engine.dispose()

    db_module._engine = None
    db_module._session_factory = None


async def _seed_state(engine, *, expires_at) -> None:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        await s.execute(
            insert(OAuthStateORM).values(
                state=f"s-{uuid4()}", verifier=f"v-{uuid4()}", expires_at=expires_at
            )
        )
        await s.commit()


async def _count(engine) -> int:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        rows = (await s.execute(select(OAuthStateORM))).scalars().all()
        return len(rows)


async def test_cleanup_deletes_only_expired_states(clean_db) -> None:
    now = datetime.now(timezone.utc)
    for _ in range(4):
        await _seed_state(clean_db, expires_at=now - timedelta(minutes=10))
    for _ in range(2):
        await _seed_state(clean_db, expires_at=now + timedelta(minutes=10))

    from app.infrastructure.jobs.oauth_state_cleanup import cleanup_expired_oauth_states

    deleted = cleanup_expired_oauth_states()
    assert deleted == 4
    assert await _count(clean_db) == 2


async def test_cleanup_returns_zero_when_nothing_expired(clean_db) -> None:
    from app.infrastructure.jobs.oauth_state_cleanup import cleanup_expired_oauth_states

    assert cleanup_expired_oauth_states() == 0
