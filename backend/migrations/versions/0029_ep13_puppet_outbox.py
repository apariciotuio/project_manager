"""EP-13 — Puppet sync outbox + sync state.

Revision ID: 0029_puppet_outbox
Revises: 0028_integration_exports
Create Date: 2026-04-16

outbox pattern for Puppet index updates: domain services enqueue rows, a
Celery worker drains them and calls PuppetClient.index / delete. Dead-lettered
rows stay with status='failed' for manual replay.
"""
from __future__ import annotations

from alembic import op

revision = "0029_puppet_outbox"
down_revision = "0028_integration_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE puppet_sync_outbox (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id   UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            work_item_id   UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            operation      VARCHAR(16) NOT NULL,
            payload        JSONB NOT NULL DEFAULT '{}'::jsonb,
            status         VARCHAR(16) NOT NULL DEFAULT 'pending',
            attempts       INTEGER NOT NULL DEFAULT 0,
            last_error     TEXT,
            enqueued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at   TIMESTAMPTZ,

            CONSTRAINT puppet_sync_outbox_operation_valid
                CHECK (operation IN ('index', 'delete')),
            CONSTRAINT puppet_sync_outbox_status_valid
                CHECK (status IN ('pending', 'in_flight', 'success', 'failed'))
        )
    """)
    op.execute(
        "CREATE INDEX idx_puppet_sync_outbox_pending "
        "ON puppet_sync_outbox(enqueued_at) WHERE status = 'pending'"
    )
    op.execute(
        "CREATE INDEX idx_puppet_sync_outbox_failed "
        "ON puppet_sync_outbox(enqueued_at DESC) WHERE status = 'failed'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS puppet_sync_outbox")
