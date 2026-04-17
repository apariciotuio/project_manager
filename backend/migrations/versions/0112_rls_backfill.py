"""MF-1 — RLS backfill on 9 workspace-scoped tables.

Revision ID: 0112_rls_backfill
Revises: 0111_ep10_validation_tpl
Create Date: 2026-04-17

Tables added in 0012/0025/0026/0027/0028/0111 have workspace_id but no
ENABLE ROW LEVEL SECURITY or CREATE POLICY. This migration closes that gap.

Special case — validation_rule_templates: workspace_id is nullable (global
system templates have workspace_id IS NULL). The policy permits reads of both
global templates AND workspace-scoped templates.

Also drops the 'vrt_global_allowed' placeholder CHECK constraint from orm.py
that served only as documentation while RLS was pending.

References: EP-12, EP-10, EP-08 — MF-1 in session-2026-04-17-mega-review.md
"""

from __future__ import annotations

from alembic import op

revision = "0112_rls_backfill"
down_revision = "0111_ep10_validation_tpl"
branch_labels = None
depends_on = None

# Tables that get the standard policy: workspace_id IS NOT NULL
_STANDARD_TABLES = (
    "teams",
    "notifications",
    "saved_searches",
    "projects",
    "routing_rules",
    "integration_configs",
    "integration_exports",
    "work_item_drafts",
)


def upgrade() -> None:
    # Standard isolation policy — workspace_id is NOT NULL on all these tables
    for table in _STANDARD_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_workspace_isolation ON {table}
                USING (workspace_id::text = current_setting('app.current_workspace', true))
        """)

    # validation_rule_templates — workspace_id is nullable (global templates)
    op.execute("ALTER TABLE validation_rule_templates ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY validation_rule_templates_workspace_isolation
            ON validation_rule_templates
            USING (
                workspace_id IS NULL
                OR workspace_id::text = current_setting('app.current_workspace', true)
            )
    """)

    # Drop the placeholder CHECK constraint that documented global-template intent
    op.execute(
        "ALTER TABLE validation_rule_templates "
        "DROP CONSTRAINT IF EXISTS vrt_global_allowed"
    )


def downgrade() -> None:
    # Restore placeholder CHECK (so downgrade is fully reversible)
    op.execute(
        "ALTER TABLE validation_rule_templates "
        "ADD CONSTRAINT vrt_global_allowed CHECK (workspace_id IS NULL OR true)"
    )

    op.execute(
        "DROP POLICY IF EXISTS validation_rule_templates_workspace_isolation "
        "ON validation_rule_templates"
    )
    op.execute("ALTER TABLE validation_rule_templates DISABLE ROW LEVEL SECURITY")

    for table in reversed(_STANDARD_TABLES):
        op.execute(
            f"DROP POLICY IF EXISTS {table}_workspace_isolation ON {table}"
        )
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
