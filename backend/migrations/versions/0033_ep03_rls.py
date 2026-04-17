"""EP-03 code-review MF-1: add workspace_id + RLS to the 3 Dundun-era tables.

Adds workspace scoping to `conversation_threads`, `assistant_suggestions`,
and `gap_findings`. Mirrors the pattern used on `work_items` (0009_create_work_items):

    workspace_id UUID NOT NULL REFERENCES workspaces(id)
    + btree index
    + RLS policy: workspace_id::text = current_setting('app.current_workspace', true)

Backfill strategy:
  - assistant_suggestions → join work_items.workspace_id (FK NOT NULL, always resolvable)
  - gap_findings        → join work_items.workspace_id (FK NOT NULL, always resolvable)
  - conversation_threads → prefer work_items.workspace_id when thread is pinned to a
    work item; otherwise fall back to the thread owner's first active workspace
    membership. Rows that still can't resolve are deleted — they represent an
    impossible "orphan thread with no workspace link" state.
"""
from __future__ import annotations

from alembic import op

revision = "0033_ep03_rls"
down_revision = "0032_team_memberships_idx"
branch_labels = None
depends_on = None


_TABLES = ("conversation_threads", "assistant_suggestions", "gap_findings")


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. Add nullable workspace_id columns so backfill can run without NOT NULL
    # -----------------------------------------------------------------
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id UUID")

    # -----------------------------------------------------------------
    # 2. Backfill
    # -----------------------------------------------------------------
    op.execute("""
        UPDATE assistant_suggestions asg
        SET workspace_id = wi.workspace_id
        FROM work_items wi
        WHERE asg.work_item_id = wi.id
    """)
    op.execute("""
        UPDATE gap_findings gf
        SET workspace_id = wi.workspace_id
        FROM work_items wi
        WHERE gf.work_item_id = wi.id
    """)
    # Threads pinned to a work item
    op.execute("""
        UPDATE conversation_threads ct
        SET workspace_id = wi.workspace_id
        FROM work_items wi
        WHERE ct.work_item_id = wi.id
          AND ct.workspace_id IS NULL
    """)
    # Threads without a work item: use owner's first active workspace
    op.execute("""
        UPDATE conversation_threads ct
        SET workspace_id = wm.workspace_id
        FROM workspace_memberships wm
        WHERE wm.user_id = ct.user_id
          AND wm.state = 'active'
          AND ct.workspace_id IS NULL
    """)
    # Drop any remaining orphan threads (no work item, user has no active workspace)
    op.execute("DELETE FROM conversation_threads WHERE workspace_id IS NULL")

    # -----------------------------------------------------------------
    # 3. Enforce NOT NULL + FK + index + RLS
    # -----------------------------------------------------------------
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_workspace_id_fkey "
            f"FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT"
        )
        op.execute(f"CREATE INDEX idx_{table}_workspace ON {table} (workspace_id)")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_workspace_isolation ON {table}
                USING (workspace_id::text = current_setting('app.current_workspace', true))
        """)


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_workspace_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_workspace")
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {table}_workspace_id_fkey")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS workspace_id")
