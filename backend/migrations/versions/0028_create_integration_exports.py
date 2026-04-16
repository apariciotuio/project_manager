"""EP-11 — integration_exports table.

Revision ID: 0028_integration_exports
Revises: 0027_projects_routing
Create Date: 2026-04-16

Audit log of Jira (and other) upserts. upsert-by-external_key lets us detect
divergence: if external record was edited externally since our last export,
we warn and require explicit confirm before re-export.
"""
from __future__ import annotations

from alembic import op

revision = "0028_integration_exports"
down_revision = "0027_projects_routing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE integration_exports (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            integration_config_id  UUID NOT NULL REFERENCES integration_configs(id)
                ON DELETE CASCADE,
            work_item_id           UUID NOT NULL REFERENCES work_items(id)
                ON DELETE CASCADE,
            workspace_id           UUID NOT NULL REFERENCES workspaces(id)
                ON DELETE CASCADE,
            external_key           VARCHAR(128) NOT NULL,
            external_url           TEXT,
            direction              VARCHAR(16) NOT NULL,
            snapshot               JSONB NOT NULL,
            status                 VARCHAR(16) NOT NULL,
            error_message          TEXT,
            exported_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            exported_by            UUID NOT NULL REFERENCES users(id),

            CONSTRAINT integration_exports_direction_valid
                CHECK (direction IN ('export', 'import')),
            CONSTRAINT integration_exports_status_valid
                CHECK (status IN ('pending', 'success', 'failed', 'conflict'))
        )
    """)
    op.execute(
        "CREATE INDEX idx_integration_exports_work_item "
        "ON integration_exports(work_item_id, exported_at DESC)"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_integration_exports_external_key "
        "ON integration_exports(integration_config_id, external_key) "
        "WHERE status = 'success'"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_exports")
