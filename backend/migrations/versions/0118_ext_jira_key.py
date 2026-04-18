"""Add external_jira_key column to work_items.

Revision ID: 0118_ext_jira_key
Revises: 0117_rls_ep03_ep04
Create Date: 2026-04-18

Adds a dedicated VARCHAR(32) column for Jira issue keys (e.g. PROJ-123).
Data migration copies values from export_reference where they look like Jira
keys (contain a hyphen). export_reference is left intact for backward compat.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0118_ext_jira_key"
down_revision = "0117_rls_ep03_ep04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "work_items",
        sa.Column("external_jira_key", sa.String(32), nullable=True),
    )

    # Partial index — only rows where the column is set, matching lookup patterns.
    op.create_index(
        "ix_work_items_external_jira_key",
        "work_items",
        ["external_jira_key"],
        postgresql_where=sa.text("external_jira_key IS NOT NULL"),
    )

    # Data migration: copy Jira-looking values from export_reference.
    # A Jira key always contains a hyphen (PROJECT-123).
    op.execute(
        """
        UPDATE work_items
        SET external_jira_key = export_reference
        WHERE export_reference LIKE '%-%'
          AND external_jira_key IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_work_items_external_jira_key", table_name="work_items")
    op.drop_column("work_items", "external_jira_key")
