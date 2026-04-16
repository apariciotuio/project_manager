"""EP-03 Phase 1b — create assistant_suggestions table.

Revision ID: 0015_create_assistant_suggestions
Revises: 0014_create_conversation_threads
Create Date: 2026-04-16

Flat table for AI-generated content suggestions. Each row represents one
proposed change to a section of a work item, produced in a batch request to
Dundun.

NOTE: section_id is stored as a bare UUID with NO foreign key constraint.
      The work_item_sections table is introduced in EP-04. The FK will be
      added in a future migration once that table exists.

Status lifecycle: pending → accepted | rejected | expired
Expiry is enforced at application level; the expires_at column is used by a
scheduled cleanup job to mark/delete stale suggestions.
"""
from __future__ import annotations

from alembic import op

revision = "0015_assistant_suggestions"
down_revision = "0014_conversation_threads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE assistant_suggestions (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id            UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            thread_id               UUID REFERENCES conversation_threads(id) ON DELETE SET NULL,
            -- section_id has NO FK: work_item_sections lands in EP-04
            section_id              UUID,
            proposed_content        TEXT NOT NULL,
            current_content         TEXT NOT NULL,
            rationale               TEXT,
            status                  VARCHAR(20) NOT NULL DEFAULT 'pending',
            version_number_target   INTEGER NOT NULL,
            batch_id                UUID NOT NULL,
            dundun_request_id       TEXT,
            created_by              UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at              TIMESTAMPTZ NOT NULL,

            CONSTRAINT assistant_suggestions_status_valid
                CHECK (status IN ('pending', 'accepted', 'rejected', 'expired'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_as_work_item_batch
            ON assistant_suggestions(work_item_id, batch_id, status)
    """)

    op.execute("""
        CREATE INDEX idx_as_work_item_created
            ON assistant_suggestions(work_item_id, created_at DESC)
    """)

    op.execute("""
        CREATE INDEX idx_as_batch
            ON assistant_suggestions(batch_id)
    """)

    op.execute("""
        CREATE INDEX idx_as_dundun_request
            ON assistant_suggestions(dundun_request_id)
            WHERE dundun_request_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_as_dundun_request")
    op.execute("DROP INDEX IF EXISTS idx_as_batch")
    op.execute("DROP INDEX IF EXISTS idx_as_work_item_created")
    op.execute("DROP INDEX IF EXISTS idx_as_work_item_batch")
    op.execute("DROP TABLE IF EXISTS assistant_suggestions")
