"""EP-00: create audit_events table (unified, append-only).

Revision ID: 0005_audit_events
Revises: 0004_memberships
Create Date: 2026-04-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_audit_events"
down_revision = "0004_memberships"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column(
            "actor_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("actor_display", sa.Text(), nullable=True),
        sa.Column(
            "workspace_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=True),
        sa.Column("entity_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("before_value", postgresql.JSONB(), nullable=True),
        sa.Column("after_value", postgresql.JSONB(), nullable=True),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "category IN ('auth','admin','domain')", name="audit_events_category_check"
        ),
    )
    op.create_index(
        "idx_audit_events_actor",
        "audit_events",
        ["workspace_id", "actor_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_audit_events_entity",
        "audit_events",
        ["workspace_id", "entity_type", "entity_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_audit_events_action",
        "audit_events",
        ["workspace_id", "action", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_audit_events_category",
        "audit_events",
        ["category", sa.text("created_at DESC")],
    )

    # Append-only: reject UPDATE and DELETE at the storage layer.
    op.execute("CREATE RULE no_update_audit AS ON UPDATE TO audit_events DO INSTEAD NOTHING")
    op.execute("CREATE RULE no_delete_audit AS ON DELETE TO audit_events DO INSTEAD NOTHING")


def downgrade() -> None:
    op.execute("DROP RULE IF EXISTS no_delete_audit ON audit_events")
    op.execute("DROP RULE IF EXISTS no_update_audit ON audit_events")
    op.drop_index("idx_audit_events_category", table_name="audit_events")
    op.drop_index("idx_audit_events_action", table_name="audit_events")
    op.drop_index("idx_audit_events_entity", table_name="audit_events")
    op.drop_index("idx_audit_events_actor", table_name="audit_events")
    op.drop_table("audit_events")
