"""EP-00 migrations integration tests.

Verifies the full `alembic upgrade head` succeeds against a clean Postgres, every
expected table/index lands, and the append-only invariant on `audit_events` holds.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import create_async_engine


@pytest_asyncio.fixture
async def engine(migrated_database):
    eng = create_async_engine(migrated_database.database.url)
    try:
        yield eng
    finally:
        await eng.dispose()


EXPECTED_TABLES = {
    "users",
    "sessions",
    "workspaces",
    "workspace_memberships",
    "audit_events",
    "oauth_states",
}


async def test_every_ep00_table_exists(engine) -> None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
        )
        present = {row[0] for row in result}
    missing = EXPECTED_TABLES - present
    assert not missing, f"missing tables after migration: {missing}"


async def test_users_rejects_invalid_status(engine) -> None:
    async with engine.begin() as conn:
        with pytest.raises(Exception, match="users_status_check|check constraint"):
            await conn.execute(
                text(
                    "INSERT INTO users (google_sub, email, full_name, status) "
                    "VALUES ('sub-1','a@tuio.com','A','banana')"
                )
            )


async def test_workspace_memberships_rejects_invalid_state(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 's2', 'b@tuio.com', 'B')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'Acme', 'acme', id FROM users WHERE email='b@tuio.com'"
            )
        )
        with pytest.raises(Exception, match="workspace_memberships_state_check|check constraint"):
            await conn.execute(
                text(
                    "INSERT INTO workspace_memberships (workspace_id, user_id, state) "
                    "SELECT w.id, u.id, 'banana' "
                    "FROM workspaces w, users u WHERE u.email='b@tuio.com' AND w.slug='acme'"
                )
            )


async def test_audit_events_update_raises(engine) -> None:
    """After 0007: UPDATE on audit_events raises an exception (trigger, not silent rule)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_events (category, action, context) "
                "VALUES ('auth','login_success','{}'::jsonb)"
            )
        )

    async with engine.connect() as conn:
        with pytest.raises(Exception, match="append-only|audit_events"):
            await conn.execute(
                text("UPDATE audit_events SET action = 'tampered'")
            )


async def test_audit_events_delete_raises(engine) -> None:
    """After 0007: DELETE on audit_events raises an exception (trigger, not silent rule)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_events (category, action, context) "
                "VALUES ('auth','login_success','{}'::jsonb)"
            )
        )

    async with engine.connect() as conn:
        with pytest.raises(Exception, match="append-only|audit_events"):
            await conn.execute(text("DELETE FROM audit_events"))


async def test_one_active_default_membership_per_user(engine) -> None:
    """Partial unique index prevents two active-default memberships for the same user."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-def', 'def@tuio.com', 'Def')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'WS1', 'ws1-def', id FROM users WHERE email='def@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'WS2', 'ws2-def', id FROM users WHERE email='def@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role, state, is_default) "
                "SELECT w.id, u.id, 'member', 'active', TRUE "
                "FROM workspaces w, users u "
                "WHERE u.email='def@tuio.com' AND w.slug='ws1-def'"
            )
        )
        with pytest.raises(Exception, match="unique|uq_default_active_membership"):
            await conn.execute(
                text(
                    "INSERT INTO workspace_memberships (workspace_id, user_id, role, state, is_default) "
                    "SELECT w.id, u.id, 'member', 'active', TRUE "
                    "FROM workspaces w, users u "
                    "WHERE u.email='def@tuio.com' AND w.slug='ws2-def'"
                )
            )


async def test_email_case_insensitive_uniqueness(engine) -> None:
    """uq_users_email_lower prevents same email with different casing."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-case1', 'Case@tuio.com', 'C1')"
            )
        )
        with pytest.raises(Exception, match="unique|uq_users_email_lower"):
            await conn.execute(
                text(
                    "INSERT INTO users (id, google_sub, email, full_name) "
                    "VALUES (gen_random_uuid(), 'sub-case2', 'case@tuio.com', 'C2')"
                )
            )


async def test_oauth_states_primary_key_on_state(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO oauth_states (state, verifier, expires_at) "
                "VALUES ('abc', 'ver1', now() + interval '5 min')"
            )
        )
        with pytest.raises(Exception, match="duplicate key|unique"):
            await conn.execute(
                text(
                    "INSERT INTO oauth_states (state, verifier, expires_at) "
                    "VALUES ('abc', 'ver2', now() + interval '5 min')"
                )
            )


async def test_oauth_states_has_return_to_column(engine) -> None:
    """0007 adds return_to and last_chosen_workspace_id to oauth_states."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO oauth_states (state, verifier, expires_at, return_to) "
                "VALUES ('rt-test', 'v1', now() + interval '5 min', '/workspace/foo')"
            )
        )
        row = (
            await conn.execute(
                text("SELECT return_to FROM oauth_states WHERE state='rt-test'")
            )
        ).one()
        assert row[0] == "/workspace/foo"
