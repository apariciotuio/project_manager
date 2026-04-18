"""EP-22 — Add primer_sent_at to conversation_threads.

Revision ID: 0122_ep22_primer_sent_at
Revises: 0121_ep10_admin_rules_jira_support
Create Date: 2026-04-18

Changes:
  1. ALTER TABLE conversation_threads ADD COLUMN primer_sent_at TIMESTAMPTZ NULL
  2. Partial index WHERE primer_sent_at IS NULL (cheap — helps the retry path)
"""
from __future__ import annotations

from alembic import op

revision = "0122_ep22_primer_sent_at"
down_revision = "0121_ep10_admin_rules_jira_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE conversation_threads
            ADD COLUMN IF NOT EXISTS primer_sent_at TIMESTAMPTZ NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversation_threads_primer_not_sent
            ON conversation_threads (id)
            WHERE primer_sent_at IS NULL
    """)


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS idx_conversation_threads_primer_not_sent"
    )
    op.execute(
        "ALTER TABLE conversation_threads DROP COLUMN IF EXISTS primer_sent_at"
    )
