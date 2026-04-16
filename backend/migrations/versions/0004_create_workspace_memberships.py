"""EP-00: create workspace_memberships table.

Revision ID: 0004_memberships
Revises: 0003_workspaces
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_memberships"
down_revision = "0003_workspaces"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace_memberships",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'member'"),
        ),
        sa.Column(
            "state",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "joined_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_membership_ws_user"),
        sa.CheckConstraint(
            "state IN ('invited','active','suspended','deleted')",
            name="workspace_memberships_state_check",
        ),
    )
    op.create_index(
        "idx_workspace_memberships_user_id", "workspace_memberships", ["user_id"]
    )
    op.create_index(
        "idx_workspace_memberships_workspace_state",
        "workspace_memberships",
        ["workspace_id", "state"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_workspace_memberships_workspace_state", table_name="workspace_memberships"
    )
    op.drop_index(
        "idx_workspace_memberships_user_id", table_name="workspace_memberships"
    )
    op.drop_table("workspace_memberships")
