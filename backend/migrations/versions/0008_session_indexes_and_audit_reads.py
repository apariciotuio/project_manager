"""EP-00 post-review hardening round 2 — indexes and ORM alignment.

Revision ID: 0008_indexes
Revises: 0007_hardening
Create Date: 2026-04-15

Changes:
  J. Partial index on sessions (user_id, expires_at DESC) WHERE revoked_at IS NULL
  K. Composite index on workspace_memberships (user_id, state); drop user_id-only index
  L. Drop idx_audit_events_category (no read path exists yet)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_indexes"
down_revision = "0007_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # J. Partial index for session lookup hot path
    # -------------------------------------------------------------------------
    op.execute(
        """
        CREATE INDEX idx_sessions_user_active
        ON sessions (user_id, expires_at DESC)
        WHERE revoked_at IS NULL
        """
    )

    # -------------------------------------------------------------------------
    # K. Composite (user_id, state) for membership queries; drop user_id-only
    # -------------------------------------------------------------------------
    op.drop_index("idx_workspace_memberships_user_id", table_name="workspace_memberships")
    op.create_index(
        "idx_workspace_memberships_user_state",
        "workspace_memberships",
        ["user_id", "state"],
    )

    # -------------------------------------------------------------------------
    # L. Drop audit category index — no read path, defer until EP-10+
    # -------------------------------------------------------------------------
    op.drop_index("idx_audit_events_category", table_name="audit_events")


def downgrade() -> None:
    # L. Restore audit category index
    op.create_index(
        "idx_audit_events_category",
        "audit_events",
        ["category", sa.text("created_at DESC")],
    )

    # K. Restore user_id-only index; drop composite
    op.drop_index("idx_workspace_memberships_user_state", table_name="workspace_memberships")
    op.create_index(
        "idx_workspace_memberships_user_id",
        "workspace_memberships",
        ["user_id"],
    )

    # J. Drop partial index
    op.drop_index("idx_sessions_user_active", table_name="sessions")
