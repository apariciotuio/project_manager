"""Add archived_at to notifications.

ORM drift fix: Notification domain + ORM already have archived_at for inbox
archive flow (EP-21 / EP-08). Migration was missing — runtime failed on list_inbox
with `column notifications.archived_at does not exist`.

Revision ID: 0113_notif_archived_at
Revises: 0112_rls_backfill
Create Date: 2026-04-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0113_notif_archived_at"
down_revision = "0112_rls_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_notifications_archived",
        "notifications",
        ["workspace_id", "recipient_id", "archived_at"],
        postgresql_where=sa.text("archived_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_archived", table_name="notifications")
    op.drop_column("notifications", "archived_at")
