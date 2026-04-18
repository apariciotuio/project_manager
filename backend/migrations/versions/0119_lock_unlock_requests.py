"""EP-17 — lock_unlock_requests table.

Revision ID: 0119_lock_unlock_requests
Revises: 0118_ext_jira_key
Create Date: 2026-04-18
"""
from __future__ import annotations

from alembic import op

revision = "0119_lock_unlock_requests"
down_revision = "0118_ext_jira_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE lock_unlock_requests (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            section_id    UUID NOT NULL REFERENCES work_item_sections(id) ON DELETE CASCADE,
            requester_id  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            reason        TEXT NOT NULL,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            responded_at  TIMESTAMPTZ NULL,
            response      TEXT NULL CHECK (response IN ('accepted', 'declined')),
            response_note TEXT NULL
        )
    """)
    op.execute("""
        CREATE INDEX idx_lock_unlock_requests_section_pending
        ON lock_unlock_requests (section_id, created_at DESC)
        WHERE responded_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS lock_unlock_requests")
