"""Migration 0112 — RLS backfill on 9 workspace-scoped tables.

Verifies workspace isolation for teams, notifications, and projects using the
non-superuser wmp_app role (RLS is bypassed for superusers).

Pattern: insert rows as superuser, query as wmp_app with a different workspace
set in app.current_workspace — expect 0 rows visible.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _insert_workspace_and_user(conn, slug: str) -> tuple[str, str]:
    """Insert a workspace+user, return (workspace_id, user_id) as str UUIDs."""
    user_row = (
        await conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, full_name) "
                "VALUES (gen_random_uuid(), :sub, :email, :name) "
                "RETURNING id"
            ),
            {"sub": f"sub-rls-{slug}", "email": f"rls-{slug}@tuio.com", "name": slug},
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
            {"name": slug, "slug": slug, "creator": user_id},
        )
    ).one()
    ws_id = str(ws_row[0])

    return ws_id, user_id


# ---------------------------------------------------------------------------
# teams isolation
# ---------------------------------------------------------------------------


async def test_teams_rls_workspace_isolation(
    db_session, rls_session
) -> None:
    """Rows in teams are invisible to a session scoped to a different workspace."""
    # Insert two workspaces + users via superuser session
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-teams-a")
        ws_b, _ = await _insert_workspace_and_user(db_session, "rls-teams-b")

        # Grant wmp_app access to the new workspaces
        await db_session.execute(
            text(
                "INSERT INTO workspace_memberships (workspace_id, user_id, role, state) "
                "VALUES (:ws, :u, 'member', 'active')"
            ),
            {"ws": ws_a, "u": user_a},
        )

        # Insert a team in workspace A
        await db_session.execute(
            text(
                "INSERT INTO teams (id, workspace_id, name, created_by) "
                "VALUES (gen_random_uuid(), :ws, 'Team Alpha', :u)"
            ),
            {"ws": ws_a, "u": user_a},
        )

    # As wmp_app, set current_workspace to workspace B — should see 0 teams from A
    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text("SELECT COUNT(*) FROM teams WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"teams RLS leaks rows across workspaces: got {count}"


async def test_teams_rls_own_workspace_visible(
    db_session, rls_session
) -> None:
    """Rows are visible when the session workspace matches."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-teams-own")
        await db_session.execute(
            text(
                "INSERT INTO teams (id, workspace_id, name, created_by) "
                "VALUES (gen_random_uuid(), :ws, 'Own Team', :u)"
            ),
            {"ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text("SELECT COUNT(*) FROM teams WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 1, f"teams RLS hides own workspace rows: got {count}"


# ---------------------------------------------------------------------------
# notifications isolation
# ---------------------------------------------------------------------------


async def test_notifications_rls_workspace_isolation(
    db_session, rls_session
) -> None:
    """Notifications in workspace A are invisible to a session scoped to workspace B."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-notif-a")
        ws_b, user_b = await _insert_workspace_and_user(db_session, "rls-notif-b")

        await db_session.execute(
            text(
                "INSERT INTO notifications "
                "(id, workspace_id, recipient_id, type, subject_type, subject_id, "
                " deeplink, idempotency_key) "
                "VALUES (gen_random_uuid(), :ws, :u, 'mention', 'work_item', "
                " gen_random_uuid(), '/item/1', 'idem-notif-a')"
            ),
            {"ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM notifications WHERE workspace_id = :ws"
                ),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"notifications RLS leaks rows: got {count}"


async def test_notifications_rls_own_workspace_visible(
    db_session, rls_session
) -> None:
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-notif-own")
        await db_session.execute(
            text(
                "INSERT INTO notifications "
                "(id, workspace_id, recipient_id, type, subject_type, subject_id, "
                " deeplink, idempotency_key) "
                "VALUES (gen_random_uuid(), :ws, :u, 'mention', 'work_item', "
                " gen_random_uuid(), '/item/2', 'idem-notif-own')"
            ),
            {"ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM notifications WHERE workspace_id = :ws"
                ),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 1, f"notifications RLS hides own rows: got {count}"


# ---------------------------------------------------------------------------
# projects isolation
# ---------------------------------------------------------------------------


async def test_projects_rls_workspace_isolation(
    db_session, rls_session
) -> None:
    """Projects in workspace A are invisible to a session scoped to workspace B."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-proj-a")
        ws_b, _ = await _insert_workspace_and_user(db_session, "rls-proj-b")

        await db_session.execute(
            text(
                "INSERT INTO projects (id, workspace_id, name, created_by) "
                "VALUES (gen_random_uuid(), :ws, 'Project Alpha', :u)"
            ),
            {"ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text("SELECT COUNT(*) FROM projects WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"projects RLS leaks rows: got {count}"


async def test_projects_rls_own_workspace_visible(
    db_session, rls_session
) -> None:
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-proj-own")
        await db_session.execute(
            text(
                "INSERT INTO projects (id, workspace_id, name, created_by) "
                "VALUES (gen_random_uuid(), :ws, 'Own Project', :u)"
            ),
            {"ws": ws_a, "u": user_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text("SELECT COUNT(*) FROM projects WHERE workspace_id = :ws"),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 1, f"projects RLS hides own rows: got {count}"


# ---------------------------------------------------------------------------
# validation_rule_templates — global (NULL workspace_id) always visible
# ---------------------------------------------------------------------------


async def test_validation_rule_templates_global_visible_to_all_workspaces(
    db_session, rls_session
) -> None:
    """Global templates (workspace_id IS NULL) visible regardless of RLS workspace."""
    async with db_session.begin():
        ws_a, _ = await _insert_workspace_and_user(db_session, "rls-vrt-global")

        await db_session.execute(
            text(
                "INSERT INTO validation_rule_templates "
                "(id, workspace_id, name, requirement_type, is_mandatory) "
                "VALUES (gen_random_uuid(), NULL, 'Global Tpl', 'section_content', true)"
            )
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_a},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM validation_rule_templates "
                    "WHERE workspace_id IS NULL AND name = 'Global Tpl'"
                )
            )
        ).scalar()

    assert count == 1, "global VRT should be visible to all workspace sessions"


async def test_validation_rule_templates_workspace_isolated(
    db_session, rls_session
) -> None:
    """Workspace-scoped VRTs are invisible from a different workspace session."""
    async with db_session.begin():
        ws_a, user_a = await _insert_workspace_and_user(db_session, "rls-vrt-a")
        ws_b, _ = await _insert_workspace_and_user(db_session, "rls-vrt-b")

        await db_session.execute(
            text(
                "INSERT INTO validation_rule_templates "
                "(id, workspace_id, name, requirement_type, is_mandatory) "
                "VALUES (gen_random_uuid(), :ws, 'WS-A Tpl', 'section_content', true)"
            ),
            {"ws": ws_a},
        )

    async with rls_session.begin():
        await rls_session.execute(
            text("SELECT set_config('app.current_workspace', :ws, true)"),
            {"ws": ws_b},
        )
        count = (
            await rls_session.execute(
                text(
                    "SELECT COUNT(*) FROM validation_rule_templates "
                    "WHERE workspace_id = :ws"
                ),
                {"ws": ws_a},
            )
        ).scalar()

    assert count == 0, f"VRT RLS leaks workspace-scoped rows: got {count}"
