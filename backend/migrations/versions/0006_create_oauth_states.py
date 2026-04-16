"""EP-00: create oauth_states table (replaces Redis state/PKCE storage — M0 descope).

Revision ID: 0006_oauth_states
Revises: 0005_audit_events
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_oauth_states"
down_revision = "0005_audit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.Text(), primary_key=True),
        sa.Column("verifier", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_oauth_states_expires_at", "oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_oauth_states_expires_at", table_name="oauth_states")
    op.drop_table("oauth_states")
