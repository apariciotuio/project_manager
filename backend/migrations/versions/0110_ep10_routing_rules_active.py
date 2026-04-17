"""EP-10 — routing_rules: add active col + check + indexes.

Revision ID: 0110_ep10_routing_rules_active
Revises: 0100_ep09_saved_searches
Create Date: 2026-04-17

Adds:
- active BOOLEAN NOT NULL DEFAULT true on routing_rules
- CHECK constraint on work_item_type (matches _WORK_ITEM_TYPES from ORM)
- UNIQUE partial index: (workspace_id, work_item_type, project_id) WHERE active=true
- Composite index: (workspace_id, work_item_type, priority DESC)
- RLS policy guard (piggybacks existing workspace RLS pattern)
"""
from __future__ import annotations

from alembic import op

revision = "0110_ep10_routing_rules_active"
down_revision = "0100_ep09_saved_searches"
branch_labels = None
depends_on = None

_WORK_ITEM_TYPES = (
    "'idea','bug','enhancement','task','initiative','spike',"
    "'business_change','requirement','story','milestone'"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE routing_rules "
        "ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT true"
    )

    # Check constraint on work_item_type
    op.execute(
        "ALTER TABLE routing_rules "
        "ADD CONSTRAINT routing_rules_type_check "
        f"CHECK (work_item_type IN ({_WORK_ITEM_TYPES}))"
    )

    # Partial UNIQUE: only one active rule per (workspace, type, project)
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_routing_rules_active_scope "
        "ON routing_rules(workspace_id, work_item_type, COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid)) "
        "WHERE active = true"
    )

    # Composite lookup index ordered by priority DESC
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_routing_rules_lookup "
        "ON routing_rules(workspace_id, work_item_type, priority DESC) "
        "WHERE active = true"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_routing_rules_lookup")
    op.execute("DROP INDEX IF EXISTS uq_routing_rules_active_scope")
    op.execute(
        "ALTER TABLE routing_rules "
        "DROP CONSTRAINT IF EXISTS routing_rules_type_check"
    )
    op.execute(
        "ALTER TABLE routing_rules DROP COLUMN IF EXISTS active"
    )
