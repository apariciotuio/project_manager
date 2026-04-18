"""RLS two-tenant isolation tests for EP-04 tables.

Migration 0117_rls_ep03_ep04 adds workspace_id + RLS to:
  work_item_sections
  work_item_section_versions
  work_item_validators
  work_item_versions

Pattern mirrors test_migration_0112_rls.py:
  - Insert rows as superuser in workspace A
  - Query as wmp_app with app.current_workspace = workspace B → 0 rows
  - Query as wmp_app with app.current_workspace = workspace A → 1 row
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_workspace_and_user(conn, slug: str) -> tuple[str, str]:
    """Return (workspace_id, user_id) as str UUIDs."""
    user_row = (
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), :sub, :email, :name) "
                "RETURNING id"
            ),
            {"sub": f"sub-rls04-{slug}", "email": f"rls04-{slug}@tuio.com", "name": slug},
        )
    ).one()
    user_id = str(user_row[0])

    ws_row = (
        await conn.execute(
            text(
                "INSERT INTO workspaces (id, name, slug, created_by) "
                "VALUES (gen_random_uuid(), :name, :slug, :creator) "
                "RETURNING id"
            ),
            {"name": slug, "slug": f"rls04-{slug}", "creator": user_id},
        )
    ).one()
    ws_id = str(ws_row[0])

    return ws_id, user_id


async def _insert_work_item(conn, ws_id: str, user_id: str, suffix: str) -> str:
    """Insert a work_item and return its id as str."""
    row = (
        await conn.execute(
            text(
                "INSERT INTO work_items "
                "(id, workspace_id, project_id, title, type, state, owner_id, creator_id) "
                "VALUES (gen_random_uuid(), :ws, gen_random_uuid(), :title, "
                "        'task', 'draft', :u, :u) "
                "RETURNING id"
            ),
            {"ws": ws_id, "title": f"Item {suffix}", "u": user_id},
        )
    ).one()
    return str(row[0])


# ---------------------------------------------------------------------------
# Parametrised two-tenant isolation check
# ---------------------------------------------------------------------------


# NOTE: work_item_section_versions requires a real section_id FK.
# The parametrised fixtures below handle simple tables directly.
# The section_versions test uses a dedicated helper.

_SIMPLE_TABLE_QUERIES: list[tuple[str, str]] = [
    (
        "work_item_sections",
        (
            "INSERT INTO work_item_sections "
            "(id, work_item_id, workspace_id, section_type, display_order, "
            " created_by, updated_by) "
            "VALUES (gen_random_uuid(), :wi, :ws, 'summary', 1, :u, :u)"
        ),
    ),
    (
        "work_item_validators",
        (
            "INSERT INTO work_item_validators "
            "(id, work_item_id, workspace_id, role, assigned_by) "
            "VALUES (gen_random_uuid(), :wi, :ws, 'reviewer', :u)"
        ),
    ),
    (
        "work_item_versions",
        (
            "INSERT INTO work_item_versions "
            "(id, work_item_id, workspace_id, version_number, snapshot, created_by) "
            "VALUES (gen_random_uuid(), :wi, :ws, 1, '{}', :u)"
        ),
    ),
]


@pytest.mark.parametrize("table,insert_sql", _SIMPLE_TABLE_QUERIES)
async def test_ep04_rls_workspace_isolation(
    db_session, rls_session, table: str, insert_sql: str
) -> None:
    """Rows in table are invisible to a session scoped to a different workspace."""
    slug_a = f"ep04-rls-{table[:8]}-a"
    slug_b = f"ep04-rls-{table[:8]}-b"

    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, slug_a)
        ws_b, _ = await _insert_workspace_and_user(db_session, slug_b)
        wi_a = await _insert_work_item(db_session, ws_a, user_a, f"{table}-a")

        await db_session.execute(
            text(insert_sql),
            {"wi": wi_a, "ws": ws_a, "u": user_a},
        )

    # Session scoped to workspace B — must see 0 rows from A
    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"{table} RLS leaks rows to workspace B: got {count}"


@pytest.mark.parametrize("table,insert_sql", _SIMPLE_TABLE_QUERIES)
async def test_ep04_rls_own_workspace_visible(
    db_session, rls_session, table: str, insert_sql: str
) -> None:
    """Rows in table are visible when the session workspace matches."""
    slug_a = f"ep04-own-{table[:8]}-a"

    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, slug_a)
        wi_a = await _insert_work_item(db_session, ws_a, user_a, f"{table}-own")

        await db_session.execute(
            text(insert_sql),
            {"wi": wi_a, "ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 1, f"{table} RLS hides own workspace rows: got {count}"


# ---------------------------------------------------------------------------
# work_item_section_versions — requires a real section_id FK
# ---------------------------------------------------------------------------


async def test_ep04_section_versions_rls_isolation(db_session, rls_session) -> None:
    """work_item_section_versions rows invisible to a different workspace session."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "ep04-secv-a")
        ws_b, _ = await _insert_workspace_and_user(db_session, "ep04-secv-b")
        wi_a = await _insert_work_item(db_session, ws_a, user_a, "secv-a")

        # Insert parent section first to satisfy FK
        sec_row = (
            await db_session.execute(
                text(
                    "INSERT INTO work_item_sections "
                    "(id, work_item_id, workspace_id, section_type, display_order, "
                    " created_by, updated_by) "
                    "VALUES (gen_random_uuid(), :wi, :ws, 'summary', 1, :u, :u) "
                    "RETURNING id"
                ),
                {"wi": wi_a, "ws": ws_a, "u": user_a},
            )
        ).one()
        sec_id = str(sec_row[0])

        await db_session.execute(
            text(
                "INSERT INTO work_item_section_versions "
                "(id, section_id, work_item_id, workspace_id, section_type, content, "
                " version, generation_source, created_by) "
                "VALUES (gen_random_uuid(), :sec, :wi, :ws, 'summary', 'v1', 1, 'manual', :u)"
            ),
            {"sec": sec_id, "wi": wi_a, "ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM work_item_section_versions "
                    "WHERE workspace_id = :ws"
                ),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"work_item_section_versions RLS leaks rows: got {count}"


async def test_ep04_section_versions_rls_own_visible(db_session, rls_session) -> None:
    """work_item_section_versions rows are visible from their own workspace session."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "ep04-secv-own")
        wi_a = await _insert_work_item(db_session, ws_a, user_a, "secv-own")

        sec_row = (
            await db_session.execute(
                text(
                    "INSERT INTO work_item_sections "
                    "(id, work_item_id, workspace_id, section_type, display_order, "
                    " created_by, updated_by) "
                    "VALUES (gen_random_uuid(), :wi, :ws, 'summary', 1, :u, :u) "
                    "RETURNING id"
                ),
                {"wi": wi_a, "ws": ws_a, "u": user_a},
            )
        ).one()
        sec_id = str(sec_row[0])

        await db_session.execute(
            text(
                "INSERT INTO work_item_section_versions "
                "(id, section_id, work_item_id, workspace_id, section_type, content, "
                " version, generation_source, created_by) "
                "VALUES (gen_random_uuid(), :sec, :wi, :ws, 'summary', 'v1', 1, 'manual', :u)"
            ),
            {"sec": sec_id, "wi": wi_a, "ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM work_item_section_versions "
                    "WHERE workspace_id = :ws"
                ),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 1, f"work_item_section_versions RLS hides own rows: got {count}"
