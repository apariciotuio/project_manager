"""EP-00 migrations integration tests.

Verifies the full `alembic upgrade head` succeeds against a clean Postgres, every
expected table/index lands, and the append-only invariant on `audit_events` holds.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
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
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
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
            await conn.execute(text("UPDATE audit_events SET action = 'tampered'"))


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
            await conn.execute(text("SELECT return_to FROM oauth_states WHERE state='rt-test'"))
        ).one()
        assert row[0] == "/workspace/foo"


# ---------------------------------------------------------------------------
# EP-03 Phase 1 — conversation_threads / assistant_suggestions / gap_findings
# ---------------------------------------------------------------------------


async def test_ep03_tables_exist(engine) -> None:
    """0014/0015/0016 migrations create three new tables."""
    expected = {"conversation_threads", "assistant_suggestions", "gap_findings"}
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
        present = {row[0] for row in result}
    missing = expected - present
    assert not missing, f"missing EP-03 tables: {missing}"


# --- conversation_threads ---


async def test_conversation_threads_columns(engine) -> None:
    """All required columns exist with correct nullability."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'conversation_threads' AND table_schema = 'public'"
            )
        )
        cols = {row[0]: row[1] for row in result}

    assert "id" in cols
    assert "user_id" in cols
    assert "work_item_id" in cols
    assert cols["work_item_id"] == "YES", "work_item_id must be NULLABLE"
    assert "dundun_conversation_id" in cols
    assert "last_message_preview" in cols
    assert "last_message_at" in cols
    assert "created_at" in cols
    assert cols["created_at"] == "NO", "created_at must be NOT NULL"
    assert "deleted_at" in cols


async def test_conversation_threads_dundun_unique(engine) -> None:
    """dundun_conversation_id has a UNIQUE constraint."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-ct1', 'ct1@tuio.com', 'CT1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'CT1-WS', 'ct1-ws', id "
                "FROM users WHERE email='ct1@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO conversation_threads "
                "(workspace_id, user_id, dundun_conversation_id) "
                "SELECT w.id, u.id, 'dun-unique-1' "
                "FROM users u, workspaces w "
                "WHERE u.email='ct1@tuio.com' AND w.slug='ct1-ws'"
            )
        )
        with pytest.raises(Exception, match="unique|duplicate"):
            await conn.execute(
                text(
                    "INSERT INTO conversation_threads "
                    "(workspace_id, user_id, dundun_conversation_id) "
                    "SELECT w.id, u.id, 'dun-unique-1' "
                    "FROM users u, workspaces w "
                    "WHERE u.email='ct1@tuio.com' AND w.slug='ct1-ws'"
                )
            )


async def test_conversation_threads_unique_user_work_item(engine) -> None:
    """At most one thread per (user_id, work_item_id) pair."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-ct2', 'ct2@tuio.com', 'CT2')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'CT-WS', 'ct-ws', id "
                "FROM users WHERE email='ct2@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'CT Item' "
                "FROM workspaces w, users u "
                "WHERE u.email='ct2@tuio.com' AND w.slug='ct-ws'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO conversation_threads "
                "(workspace_id, user_id, work_item_id, dundun_conversation_id) "
                "SELECT w.id, u.id, wi.id, 'dun-pair-1' "
                "FROM users u, work_items wi, workspaces w "
                "WHERE u.email='ct2@tuio.com' AND wi.title='CT Item' AND w.slug='ct-ws'"
            )
        )
        with pytest.raises(Exception, match="unique|duplicate"):
            await conn.execute(
                text(
                    "INSERT INTO conversation_threads "
                    "(workspace_id, user_id, work_item_id, dundun_conversation_id) "
                    "SELECT w.id, u.id, wi.id, 'dun-pair-2' "
                    "FROM users u, work_items wi, workspaces w "
                    "WHERE u.email='ct2@tuio.com' AND wi.title='CT Item' AND w.slug='ct-ws'"
                )
            )


async def test_conversation_threads_work_item_fk_set_null(engine) -> None:
    """Deleting a work_item sets conversation_threads.work_item_id to NULL."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-ct3', 'ct3@tuio.com', 'CT3')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'CT-WS3', 'ct-ws3', id "
                "FROM users WHERE email='ct3@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'CT Item3' "
                "FROM workspaces w, users u "
                "WHERE u.email='ct3@tuio.com' AND w.slug='ct-ws3'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO conversation_threads "
                "(workspace_id, user_id, work_item_id, dundun_conversation_id) "
                "SELECT w.id, u.id, wi.id, 'dun-setnull' "
                "FROM users u, work_items wi, workspaces w "
                "WHERE u.email='ct3@tuio.com' AND wi.title='CT Item3' AND w.slug='ct-ws3'"
            )
        )
        await conn.execute(text("DELETE FROM work_items WHERE title='CT Item3'"))
        row = (
            await conn.execute(
                text(
                    "SELECT work_item_id FROM conversation_threads "
                    "WHERE dundun_conversation_id='dun-setnull'"
                )
            )
        ).one()
        assert row[0] is None, "work_item_id should be NULL after work_item delete"


# --- assistant_suggestions ---


async def test_assistant_suggestions_columns(engine) -> None:
    """All required columns exist with correct nullability."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'assistant_suggestions' AND table_schema = 'public'"
            )
        )
        cols = {row[0]: row[1] for row in result}

    required_not_null = {
        "id",
        "work_item_id",
        "proposed_content",
        "current_content",
        "status",
        "version_number_target",
        "batch_id",
        "created_by",
        "created_at",
        "updated_at",
        "expires_at",
    }
    for col in required_not_null:
        assert col in cols, f"column {col} missing from assistant_suggestions"
        assert cols[col] == "NO", f"{col} must be NOT NULL"

    nullable_cols = {"thread_id", "section_id", "rationale", "dundun_request_id"}
    for col in nullable_cols:
        assert col in cols, f"nullable column {col} missing from assistant_suggestions"
        assert cols[col] == "YES", f"{col} must be NULLABLE"


async def test_assistant_suggestions_status_check(engine) -> None:
    """status column rejects values outside the allowed set."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-as1', 'as1@tuio.com', 'AS1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'AS-WS', 'as-ws', id "
                "FROM users WHERE email='as1@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'AS Item' "
                "FROM workspaces w, users u "
                "WHERE u.email='as1@tuio.com' AND w.slug='as-ws'"
            )
        )
        with pytest.raises(Exception, match="check|constraint"):
            await conn.execute(
                text(
                    "INSERT INTO assistant_suggestions "
                    "(workspace_id, work_item_id, proposed_content, current_content, status, "
                    " version_number_target, batch_id, created_by, expires_at) "
                    "SELECT w.id, wi.id, 'p', 'c', 'invalid', 1, gen_random_uuid(), u.id, "
                    "       now() + interval '1 day' "
                    "FROM work_items wi, users u, workspaces w "
                    "WHERE u.email='as1@tuio.com' AND wi.title='AS Item' AND w.slug='as-ws'"
                )
            )


async def test_assistant_suggestions_status_default_pending(engine) -> None:
    """status defaults to 'pending' when not specified."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-as2', 'as2@tuio.com', 'AS2')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'AS-WS2', 'as-ws2', id "
                "FROM users WHERE email='as2@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'AS Item2' "
                "FROM workspaces w, users u "
                "WHERE u.email='as2@tuio.com' AND w.slug='as-ws2'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO assistant_suggestions "
                "(workspace_id, work_item_id, proposed_content, current_content, "
                " version_number_target, batch_id, created_by, expires_at) "
                "SELECT w.id, wi.id, 'prop', 'curr', 1, gen_random_uuid(), u.id, "
                "       now() + interval '1 day' "
                "FROM work_items wi, users u, workspaces w "
                "WHERE u.email='as2@tuio.com' AND wi.title='AS Item2' AND w.slug='as-ws2'"
            )
        )
        row = (
            await conn.execute(
                text(
                    "SELECT status FROM assistant_suggestions "
                    "WHERE work_item_id = ("
                    "  SELECT wi.id FROM work_items wi WHERE wi.title='AS Item2'"
                    ")"
                )
            )
        ).one()
        assert row[0] == "pending"


async def test_assistant_suggestions_indexes_exist(engine) -> None:
    """Required indexes on assistant_suggestions are present."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'assistant_suggestions' AND schemaname = 'public'"
            )
        )
        indexes = {row[0] for row in result}

    for expected in (
        "idx_as_work_item_batch",
        "idx_as_work_item_created",
        "idx_as_batch",
        "idx_as_dundun_request",
    ):
        assert expected in indexes, f"missing index: {expected}"


async def test_assistant_suggestions_work_item_fk_cascade(engine) -> None:
    """Deleting a work_item cascades to assistant_suggestions."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-as3', 'as3@tuio.com', 'AS3')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'AS-WS3', 'as-ws3', id "
                "FROM users WHERE email='as3@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'AS Item3' "
                "FROM workspaces w, users u "
                "WHERE u.email='as3@tuio.com' AND w.slug='as-ws3'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO assistant_suggestions "
                "(workspace_id, work_item_id, proposed_content, current_content, "
                " version_number_target, batch_id, created_by, expires_at) "
                "SELECT w.id, wi.id, 'p3', 'c3', 1, gen_random_uuid(), u.id, "
                "       now() + interval '1 day' "
                "FROM work_items wi, users u, workspaces w "
                "WHERE u.email='as3@tuio.com' AND wi.title='AS Item3' AND w.slug='as-ws3'"
            )
        )
        await conn.execute(text("DELETE FROM work_items WHERE title='AS Item3'"))
        count = (
            await conn.execute(
                text("SELECT COUNT(*) FROM assistant_suggestions WHERE proposed_content='p3'")
            )
        ).scalar()
        assert count == 0, "cascade delete from work_items to assistant_suggestions failed"


# --- gap_findings ---


async def test_gap_findings_columns(engine) -> None:
    """All required columns exist with correct nullability."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT column_name, is_nullable "
                "FROM information_schema.columns "
                "WHERE table_name = 'gap_findings' AND table_schema = 'public'"
            )
        )
        cols = {row[0]: row[1] for row in result}

    required_not_null = {
        "id",
        "work_item_id",
        "source",
        "severity",
        "dimension",
        "message",
        "created_at",
    }
    for col in required_not_null:
        assert col in cols, f"column {col} missing from gap_findings"
        assert cols[col] == "NO", f"{col} must be NOT NULL"

    nullable_cols = {"dundun_request_id", "invalidated_at"}
    for col in nullable_cols:
        assert col in cols, f"nullable column {col} missing from gap_findings"
        assert cols[col] == "YES", f"{col} must be NULLABLE"


async def test_gap_findings_source_check(engine) -> None:
    """source column rejects values outside (rule, dundun)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-gf1', 'gf1@tuio.com', 'GF1')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'GF-WS', 'gf-ws', id "
                "FROM users WHERE email='gf1@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'GF Item' "
                "FROM workspaces w, users u "
                "WHERE u.email='gf1@tuio.com' AND w.slug='gf-ws'"
            )
        )
        with pytest.raises(Exception, match="check|constraint"):
            await conn.execute(
                text(
                    "INSERT INTO gap_findings "
                    "(workspace_id, work_item_id, source, severity, dimension, message) "
                    "SELECT w.id, wi.id, 'invalid', 'warning', 'dim', 'msg' "
                    "FROM work_items wi, workspaces w "
                    "WHERE wi.title='GF Item' AND w.slug='gf-ws'"
                )
            )


async def test_gap_findings_severity_check(engine) -> None:
    """severity column rejects values outside (blocking, warning, info)."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-gf2', 'gf2@tuio.com', 'GF2')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'GF-WS2', 'gf-ws2', id "
                "FROM users WHERE email='gf2@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'GF Item2' "
                "FROM workspaces w, users u "
                "WHERE u.email='gf2@tuio.com' AND w.slug='gf-ws2'"
            )
        )
        with pytest.raises(Exception, match="check|constraint"):
            await conn.execute(
                text(
                    "INSERT INTO gap_findings "
                    "(workspace_id, work_item_id, source, severity, dimension, message) "
                    "SELECT w.id, wi.id, 'rule', 'critical', 'dim', 'msg' "
                    "FROM work_items wi, workspaces w "
                    "WHERE wi.title='GF Item2' AND w.slug='gf-ws2'"
                )
            )


async def test_gap_findings_indexes_exist(engine) -> None:
    """Required indexes on gap_findings are present."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT indexname FROM pg_indexes "
                "WHERE tablename = 'gap_findings' AND schemaname = 'public'"
            )
        )
        indexes = {row[0] for row in result}

    assert "idx_gap_findings_work_item" in indexes, "missing idx_gap_findings_work_item"
    assert "idx_gap_findings_active" in indexes, "missing idx_gap_findings_active"


async def test_gap_findings_work_item_fk_cascade(engine) -> None:
    """Deleting a work_item cascades to gap_findings."""
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), 'sub-gf3', 'gf3@tuio.com', 'GF3')"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "SELECT gen_random_uuid(), 'GF-WS3', 'gf-ws3', id "
                "FROM users WHERE email='gf3@tuio.com'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO work_items (id, workspace_id, project_id, creator_id, owner_id, type, state, title) "
                "SELECT gen_random_uuid(), w.id, gen_random_uuid(), u.id, u.id, 'task', 'draft', 'GF Item3' "
                "FROM workspaces w, users u "
                "WHERE u.email='gf3@tuio.com' AND w.slug='gf-ws3'"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO gap_findings "
                "(workspace_id, work_item_id, source, severity, dimension, message) "
                "SELECT w.id, wi.id, 'rule', 'warning', 'dim', 'msg' "
                "FROM work_items wi, workspaces w "
                "WHERE wi.title='GF Item3' AND w.slug='gf-ws3'"
            )
        )
        await conn.execute(text("DELETE FROM work_items WHERE title='GF Item3'"))
        count = (
            await conn.execute(
                text(
                    "SELECT COUNT(*) FROM gap_findings WHERE dimension='dim' AND message='msg' "
                    "AND work_item_id NOT IN (SELECT id FROM work_items)"
                )
            )
        ).scalar()
        assert count == 0, "cascade delete from work_items to gap_findings failed"
