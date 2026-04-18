"""Add workspace_id + RLS to EP-04 tables.

Revision ID: 0117_rls_ep03_ep04
Revises: 0116_rate_limit_buckets
Create Date: 2026-04-18

Adds workspace scoping to the 4 EP-04 tables that were not covered by
0033_ep03_rls (which handled conversation_threads / assistant_suggestions /
gap_findings).

Tables:
  work_item_sections
  work_item_section_versions
  work_item_validators
  work_item_versions

All four tables carry work_item_id NOT NULL → work_items.workspace_id is always
resolvable.  Backfill is a single-step JOIN per table.

Pattern mirrors 0033_ep03_rls / 0009_create_work_items:
  1. Add nullable column
  2. Backfill via JOIN through work_items
  3. Enforce NOT NULL + FK
  4. Add btree index
  5. Enable RLS + create isolation policy
"""
from __future__ import annotations

from alembic import op

revision = "0117_rls_ep03_ep04"
down_revision = "0116_rate_limit_buckets"
branch_labels = None
depends_on = None


_TABLES = (
    "work_item_sections",
    "work_item_section_versions",
    "work_item_validators",
    "work_item_versions",
)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add nullable workspace_id so backfill can run without NOT NULL
    # ------------------------------------------------------------------
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN workspace_id UUID")

    # ------------------------------------------------------------------
    # 2. Backfill via work_items.workspace_id (FK always NOT NULL)
    # ------------------------------------------------------------------
    for table in _TABLES:
        op.execute(f"""
            UPDATE {table} t
            SET workspace_id = wi.workspace_id
            FROM work_items wi
            WHERE t.work_item_id = wi.id
        """)

    # ------------------------------------------------------------------
    # 3. Enforce NOT NULL + FK + index + RLS
    # ------------------------------------------------------------------
    for table in _TABLES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN workspace_id SET NOT NULL")
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {table}_workspace_id_fkey "
            f"FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE RESTRICT"
        )
        op.execute(
            f"CREATE INDEX ix_{table}_workspace_id ON {table} (workspace_id)"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_workspace_isolation ON {table}
                USING (workspace_id::text = current_setting('app.current_workspace', true))
        """)


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS {table}_workspace_isolation ON {table}"
        )
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"DROP INDEX IF EXISTS ix_{table}_workspace_id")
        op.execute(
            f"ALTER TABLE {table} "
            f"DROP CONSTRAINT IF EXISTS {table}_workspace_id_fkey"
        )
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS workspace_id")
