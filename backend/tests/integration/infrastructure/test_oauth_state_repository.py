"""OAuthStateRepositoryImpl integration tests.

Validates the `DELETE ... RETURNING verifier` atomic single-use contract and the
5-minute TTL sweep.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.domain.repositories.oauth_state_repository import (
    ConsumedOAuthState,
    OAuthStateCollisionError,
)
from app.infrastructure.persistence.oauth_state_repository_impl import (
    OAuthStateRepositoryImpl,
)


@pytest.fixture
def repo(db_session) -> OAuthStateRepositoryImpl:
    return OAuthStateRepositoryImpl(db_session)


async def test_create_then_consume_returns_verifier(repo, db_session) -> None:
    await repo.create(state="state-1", verifier="v-1", ttl_seconds=300)
    await db_session.commit()

    got = await repo.consume("state-1")
    await db_session.commit()
    assert got is not None
    assert got.verifier == "v-1"
    assert got.return_to is None
    assert got.last_chosen_workspace_id is None


async def test_create_with_return_to_and_workspace_id(repo, db_session) -> None:
    ws_id = uuid4()
    await repo.create(
        state="state-full",
        verifier="v-full",
        ttl_seconds=300,
        return_to="/workspace/foo",
        last_chosen_workspace_id=ws_id,
    )
    await db_session.commit()

    got = await repo.consume("state-full")
    await db_session.commit()
    assert isinstance(got, ConsumedOAuthState)
    assert got.verifier == "v-full"
    assert got.return_to == "/workspace/foo"
    assert got.last_chosen_workspace_id == ws_id


async def test_consume_is_single_use(repo, db_session) -> None:
    await repo.create(state="state-2", verifier="v-2", ttl_seconds=300)
    await db_session.commit()

    first = await repo.consume("state-2")
    await db_session.commit()
    second = await repo.consume("state-2")
    await db_session.commit()

    assert first is not None and first.verifier == "v-2"
    assert second is None, "second consume must not return the verifier"


async def test_consume_returns_none_for_missing(repo) -> None:
    assert await repo.consume("nope") is None


async def test_consume_returns_none_when_expired(repo, db_session) -> None:
    await repo.create(state="state-exp", verifier="v-exp", ttl_seconds=300)
    # Backdate expires_at beyond now().
    await db_session.execute(
        text("UPDATE oauth_states SET expires_at = :exp WHERE state = :s"),
        {
            "exp": datetime.now(UTC) - timedelta(seconds=1),
            "s": "state-exp",
        },
    )
    await db_session.commit()

    assert await repo.consume("state-exp") is None


async def test_cleanup_expired_removes_only_expired(repo, db_session) -> None:
    await repo.create(state="fresh", verifier="vf", ttl_seconds=300)
    await repo.create(state="stale", verifier="vs", ttl_seconds=300)
    await db_session.execute(
        text("UPDATE oauth_states SET expires_at = :exp WHERE state = 'stale'"),
        {"exp": datetime.now(UTC) - timedelta(hours=1)},
    )
    await db_session.commit()

    removed = await repo.cleanup_expired()
    await db_session.commit()
    assert removed == 1

    # `fresh` still consumable.
    got = await repo.consume("fresh")
    assert got is not None and got.verifier == "vf"


async def test_duplicate_state_raises_collision_error(repo, db_session) -> None:
    await repo.create(state="dup", verifier="v1", ttl_seconds=300)
    await db_session.commit()

    with pytest.raises(OAuthStateCollisionError):
        await repo.create(state="dup", verifier="v2", ttl_seconds=300)
