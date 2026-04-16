"""EP-02 Phase 1a — add draft_data and template_id columns to work_items.

Revision ID: 0011_draft_data_template_id
Revises: 0010_system_actor
Create Date: 2026-04-15

template_id references templates(id) which is created in 0013. We add the
column nullable first; the FK is added in 0013 after the table exists.
"""
from __future__ import annotations

from alembic import op

revision = "0011_draft_data_template_id"
down_revision = "0010_system_actor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE work_items
            ADD COLUMN IF NOT EXISTS draft_data JSONB NULL,
            ADD COLUMN IF NOT EXISTS template_id UUID NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE work_items
            DROP COLUMN IF EXISTS template_id,
            DROP COLUMN IF EXISTS draft_data
    """)
