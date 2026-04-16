"""EP-03 Phase 1a — create conversation_threads table.

Revision ID: 0014_create_conversation_threads
Revises: 0013_create_templates
Create Date: 2026-04-16

Stores the mapping between a (user, work_item) pair and a Dundun conversation
ID. The platform owns the message store; this table is a pointer-only record.

Constraints:
  - At most one thread per (user_id, work_item_id) pair — UNIQUE constraint.
  - dundun_conversation_id is globally unique (Dundun assigns it).
  - work_item_id is NULLABLE: a thread can exist without a work item (general
    assistant chat), and deletes of work_items SET NULL rather than CASCADE
    so conversation history is preserved.
  - deleted_at is a soft-archive pointer; no rows are physically removed.
"""
from __future__ import annotations

from alembic import op

revision = "0014_conversation_threads"
down_revision = "0013_create_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE conversation_threads (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id                 UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            work_item_id            UUID REFERENCES work_items(id) ON DELETE SET NULL,
            dundun_conversation_id  TEXT NOT NULL UNIQUE,
            last_message_preview    TEXT,
            last_message_at         TIMESTAMPTZ,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at              TIMESTAMPTZ,

            CONSTRAINT conversation_threads_unique_user_work_item
                UNIQUE (user_id, work_item_id)
        )
    """)

    op.execute("""
        CREATE INDEX idx_conversation_threads_user
            ON conversation_threads(user_id)
    """)

    op.execute("""
        CREATE INDEX idx_conversation_threads_work_item
            ON conversation_threads(work_item_id)
            WHERE work_item_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_threads")
