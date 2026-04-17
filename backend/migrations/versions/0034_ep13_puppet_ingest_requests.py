"""EP-13 — puppet_ingest_requests table.

Revision ID: 0034_puppet_ingest_requests
Revises: 0033_ep03_rls
Create Date: 2026-04-17

Tracks every Puppet document-ingestion request so we can:
  - Retry on failure (attempts / last_error)
  - Deduplicate on success (puppet_doc_id set)
  - Observe pipeline lag (created_at / succeeded_at)

source_kind: 'outbox' = driven by PuppetSyncOutbox drain,
             'manual' = admin-triggered reindex,
             'webhook' = future external trigger.

status transitions: queued → dispatched → succeeded | failed | skipped
                    failed → queued (manual retry resets attempts to 0)
"""
from __future__ import annotations

from alembic import op

revision = "0034_puppet_ingest_requests"
down_revision = "0033_ep03_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE puppet_ingest_requests (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            source_kind     VARCHAR(30) NOT NULL,
            work_item_id    UUID REFERENCES work_items(id) ON DELETE SET NULL,
            payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
            status          VARCHAR(20) NOT NULL DEFAULT 'queued',
            puppet_doc_id   TEXT,
            attempts        INTEGER NOT NULL DEFAULT 0,
            last_error      TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            succeeded_at    TIMESTAMPTZ,

            CONSTRAINT puppet_ingest_requests_source_kind_valid
                CHECK (source_kind IN ('outbox', 'manual', 'webhook')),
            CONSTRAINT puppet_ingest_requests_status_valid
                CHECK (status IN ('queued', 'dispatched', 'succeeded', 'failed', 'skipped'))
        )
    """)

    # Indexes
    op.execute(
        "CREATE INDEX idx_puppet_ingest_requests_ws_status "
        "ON puppet_ingest_requests (workspace_id, status)"
    )
    op.execute(
        "CREATE INDEX idx_puppet_ingest_requests_work_item "
        "ON puppet_ingest_requests (work_item_id) WHERE work_item_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_puppet_ingest_requests_created_at "
        "ON puppet_ingest_requests (created_at DESC)"
    )

    # RLS — workspace isolation
    op.execute("ALTER TABLE puppet_ingest_requests ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY puppet_ingest_requests_workspace_isolation ON puppet_ingest_requests
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS puppet_ingest_requests_workspace_isolation "
        "ON puppet_ingest_requests"
    )
    op.execute("DROP TABLE IF EXISTS puppet_ingest_requests")
