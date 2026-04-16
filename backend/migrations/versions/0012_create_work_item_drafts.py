"""EP-02 Phase 1b — create work_item_drafts table.

Revision ID: 0012_create_work_item_drafts
Revises: 0011_draft_data_template_id
Create Date: 2026-04-15

One pre-creation draft per (user_id, workspace_id). Expires after 30 days.
Celery Beat job cleans expired rows daily (see expire_drafts_task.py).
"""
from __future__ import annotations

from alembic import op

revision = "0012_create_work_item_drafts"
down_revision = "0011_draft_data_template_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE work_item_drafts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            data            JSONB NOT NULL DEFAULT '{}',
            local_version   INTEGER NOT NULL DEFAULT 1,
            incomplete      BOOLEAN NOT NULL DEFAULT TRUE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 days',

            CONSTRAINT work_item_drafts_unique_user_workspace UNIQUE (user_id, workspace_id)
        )
    """)

    # Index on expires_at for fast expired-draft queries (cleanup job)
    # Note: partial index WHERE expires_at < now() is invalid in Postgres because
    # now() is volatile. A plain index on expires_at is sufficient for the cleanup query.
    op.execute("""
        CREATE INDEX idx_work_item_drafts_expires
            ON work_item_drafts(expires_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS work_item_drafts")
