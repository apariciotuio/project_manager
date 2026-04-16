"""EP-07 — work_item_versions extension, comments, timeline_events.

Revision ID: 0024_ep07_versions_comments_timeline
Revises: 0023_create_review_and_validation
Create Date: 2026-04-16

Extends work_item_versions with EP-07's `trigger`, `actor_type`, `actor_id`,
`commit_message`, `snapshot_schema_version`, and `archived` columns.

Adds `comments` (single-level nesting, app-layer enforced; anchor columns for
inline section highlights) and the `timeline_events` outbox-driven audit log.

timeline_events.work_item_id uses ON DELETE RESTRICT to preserve audit history
even when a work item is hard-deleted by accident (normal path is soft-delete).
"""
from __future__ import annotations

from alembic import op

revision = "0024_ep07_versions_comments"
down_revision = "0023_review_and_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE work_item_versions
            ADD COLUMN snapshot_schema_version INTEGER NOT NULL DEFAULT 1,
            ADD COLUMN trigger          TEXT NOT NULL DEFAULT 'content_edit',
            ADD COLUMN actor_type       TEXT NOT NULL DEFAULT 'human',
            ADD COLUMN actor_id         UUID,
            ADD COLUMN commit_message   TEXT,
            ADD COLUMN archived         BOOLEAN NOT NULL DEFAULT false
    """)
    op.execute(
        "ALTER TABLE work_item_versions ADD CONSTRAINT work_item_versions_trigger_valid "
        "CHECK (trigger IN ('content_edit', 'state_transition', 'review_outcome', "
        "'breakdown_change', 'manual', 'ai_suggestion'))"
    )
    op.execute(
        "ALTER TABLE work_item_versions ADD CONSTRAINT work_item_versions_actor_type_valid "
        "CHECK (actor_type IN ('human', 'ai_suggestion', 'system'))"
    )
    op.execute("""
        CREATE INDEX idx_wiv_archived
        ON work_item_versions(work_item_id, archived)
        WHERE archived = false
    """)
    op.execute("""
        CREATE INDEX idx_wiv_work_item_version
        ON work_item_versions(work_item_id, version_number DESC)
        WHERE archived = false
    """)

    op.execute("""
        CREATE TABLE comments (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id           UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            parent_comment_id      UUID REFERENCES comments(id) ON DELETE SET NULL,
            body                   TEXT NOT NULL,
            actor_type             TEXT NOT NULL,
            actor_id               UUID,
            anchor_section_id      UUID REFERENCES work_item_sections(id) ON DELETE SET NULL,
            anchor_start_offset    INTEGER,
            anchor_end_offset      INTEGER,
            anchor_snapshot_text   TEXT,
            anchor_status          TEXT NOT NULL DEFAULT 'active',
            is_edited              BOOLEAN NOT NULL DEFAULT false,
            edited_at              TIMESTAMPTZ,
            deleted_at             TIMESTAMPTZ,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT comments_body_length CHECK (char_length(body) BETWEEN 1 AND 10000),
            CONSTRAINT comments_actor_type_valid CHECK (
                actor_type IN ('human', 'ai_suggestion', 'system')
            ),
            CONSTRAINT comments_anchor_status_valid CHECK (
                anchor_status IN ('active', 'orphaned')
            ),
            CONSTRAINT comments_anchor_range_valid CHECK (
                (anchor_start_offset IS NULL AND anchor_end_offset IS NULL)
                OR (anchor_start_offset >= 0 AND anchor_end_offset >= anchor_start_offset)
            ),
            CONSTRAINT comments_anchor_section_required_for_range CHECK (
                anchor_start_offset IS NULL OR anchor_section_id IS NOT NULL
            )
        )
    """)
    op.execute("CREATE INDEX idx_comments_work_item ON comments(work_item_id)")
    op.execute(
        "CREATE INDEX idx_comments_parent ON comments(parent_comment_id) "
        "WHERE parent_comment_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_comments_active ON comments(work_item_id, created_at DESC) "
        "WHERE deleted_at IS NULL"
    )

    op.execute("""
        CREATE TABLE timeline_events (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id       UUID NOT NULL REFERENCES work_items(id) ON DELETE RESTRICT,
            workspace_id       UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            event_type         TEXT NOT NULL,
            actor_type         TEXT NOT NULL,
            actor_id           UUID,
            actor_display_name TEXT,
            summary            TEXT NOT NULL,
            payload            JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            source_id          UUID,
            source_table       TEXT,

            CONSTRAINT timeline_events_summary_length CHECK (char_length(summary) <= 255),
            CONSTRAINT timeline_events_actor_type_valid CHECK (
                actor_type IN ('human', 'ai_suggestion', 'system')
            )
        )
    """)
    op.execute(
        "CREATE INDEX idx_timeline_work_item ON timeline_events"
        "(work_item_id, occurred_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_timeline_event_type ON timeline_events"
        "(work_item_id, event_type)"
    )
    op.execute(
        "CREATE INDEX idx_timeline_actor_type ON timeline_events"
        "(work_item_id, actor_type)"
    )
    op.execute(
        "CREATE INDEX idx_timeline_cursor ON timeline_events"
        "(work_item_id, occurred_at DESC, id DESC)"
    )
    op.execute(
        "CREATE INDEX idx_timeline_workspace_occurred ON timeline_events"
        "(workspace_id, occurred_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS timeline_events")
    op.execute("DROP TABLE IF EXISTS comments")
    op.execute("DROP INDEX IF EXISTS idx_wiv_work_item_version")
    op.execute("DROP INDEX IF EXISTS idx_wiv_archived")
    op.execute("""
        ALTER TABLE work_item_versions
            DROP CONSTRAINT IF EXISTS work_item_versions_actor_type_valid,
            DROP CONSTRAINT IF EXISTS work_item_versions_trigger_valid,
            DROP COLUMN IF EXISTS archived,
            DROP COLUMN IF EXISTS commit_message,
            DROP COLUMN IF EXISTS actor_id,
            DROP COLUMN IF EXISTS actor_type,
            DROP COLUMN IF EXISTS trigger,
            DROP COLUMN IF EXISTS snapshot_schema_version
    """)
