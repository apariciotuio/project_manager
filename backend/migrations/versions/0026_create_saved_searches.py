"""EP-09 — saved_searches table.

Revision ID: 0026_saved_searches
Revises: 0025_teams_notifications
Create Date: 2026-04-16
"""
from __future__ import annotations

from alembic import op

revision = "0026_saved_searches"
down_revision = "0025_teams_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE saved_searches (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name         VARCHAR(255) NOT NULL,
            query_params JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX idx_saved_searches_user ON saved_searches(user_id, workspace_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_saved_searches_user_name "
        "ON saved_searches(user_id, workspace_id, name)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS saved_searches")
