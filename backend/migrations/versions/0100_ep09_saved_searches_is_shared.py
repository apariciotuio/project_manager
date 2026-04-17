"""EP-09 — Add is_shared column to saved_searches.

Revision ID: 0100_ep09_saved_searches
Revises: 0080_applied_suggestion
Create Date: 2026-04-17
"""
from __future__ import annotations

from alembic import op

revision = "0100_ep09_saved_searches"
down_revision = "0080_applied_suggestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE saved_searches ADD COLUMN IF NOT EXISTS "
        "is_shared BOOLEAN NOT NULL DEFAULT false"
    )
    # Add composite indexes for EP-09 work_items query performance
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_items_state_updated "
        "ON work_items (state, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_items_owner_updated "
        "ON work_items (owner_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_items_state_owner "
        "ON work_items (state, owner_id, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_items_creator "
        "ON work_items (creator_id)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE saved_searches DROP COLUMN IF EXISTS is_shared"
    )
    op.execute("DROP INDEX IF EXISTS idx_work_items_state_updated")
    op.execute("DROP INDEX IF EXISTS idx_work_items_owner_updated")
    op.execute("DROP INDEX IF EXISTS idx_work_items_state_owner")
    op.execute("DROP INDEX IF EXISTS idx_work_items_creator")
