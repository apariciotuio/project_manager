"""EP-14+15+16+17 — hierarchy types, tags, attachments, locks.

Revision ID: 0030_ep14_15_16_17
Revises: 0029_puppet_outbox
Create Date: 2026-04-16

- EP-14: extends work_items.type CHECK to include 'milestone', 'story';
  parent_work_item_id already exists on work_items (EP-01 migration 0011+).
- EP-15: tags + work_item_tags many-to-many.
- EP-16: attachments for work_items + comments (CSP-friendly authenticated
  streaming endpoint wiring comes later).
- EP-17: locks table for section-level edit locks with heartbeat-based
  auto-release.
"""
from __future__ import annotations

from alembic import op

revision = "0030_ep14_15_16_17"
down_revision = "0029_puppet_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # EP-14 — extend work item types (milestone, story)
    # ------------------------------------------------------------------
    # work_items.type is VARCHAR(32). There's no existing app-layer
    # CHECK constraint in the migrations we control directly -- the app
    # layer's Enum is the source of truth. No DDL required; EP-01 WorkItem
    # enum will be extended alongside this migration.

    # ------------------------------------------------------------------
    # EP-15 — tags
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE tags (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name          VARCHAR(64) NOT NULL,
            color         VARCHAR(16),
            archived_at   TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by    UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_tags_workspace_active_name "
        "ON tags(workspace_id, lower(name)) WHERE archived_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_tags_workspace_active "
        "ON tags(workspace_id) WHERE archived_at IS NULL"
    )

    op.execute("""
        CREATE TABLE work_item_tags (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id  UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            tag_id        UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by    UUID NOT NULL REFERENCES users(id),

            CONSTRAINT uq_work_item_tag UNIQUE (work_item_id, tag_id)
        )
    """)
    op.execute("CREATE INDEX idx_work_item_tags_tag ON work_item_tags(tag_id)")

    # ------------------------------------------------------------------
    # EP-16 — attachments
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE attachments (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            work_item_id  UUID REFERENCES work_items(id) ON DELETE CASCADE,
            comment_id    UUID REFERENCES comments(id) ON DELETE CASCADE,
            filename      VARCHAR(512) NOT NULL,
            content_type  VARCHAR(128) NOT NULL,
            size_bytes    BIGINT NOT NULL,
            storage_key   TEXT NOT NULL,
            thumbnail_key TEXT,
            checksum_sha256 VARCHAR(64),
            deleted_at    TIMESTAMPTZ,
            uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            uploaded_by   UUID NOT NULL REFERENCES users(id),

            CONSTRAINT attachments_exactly_one_anchor CHECK (
                (work_item_id IS NOT NULL AND comment_id IS NULL)
                OR (comment_id IS NOT NULL AND work_item_id IS NULL)
            ),
            CONSTRAINT attachments_size_bytes_positive CHECK (size_bytes > 0)
        )
    """)
    op.execute(
        "CREATE INDEX idx_attachments_work_item "
        "ON attachments(work_item_id) WHERE deleted_at IS NULL AND work_item_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX idx_attachments_comment "
        "ON attachments(comment_id) WHERE deleted_at IS NULL AND comment_id IS NOT NULL"
    )

    # ------------------------------------------------------------------
    # EP-17 — locks
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE section_locks (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            section_id       UUID NOT NULL REFERENCES work_item_sections(id)
                ON DELETE CASCADE,
            work_item_id     UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            held_by          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            acquired_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            heartbeat_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at       TIMESTAMPTZ NOT NULL,
            force_released_at TIMESTAMPTZ,
            force_released_by UUID REFERENCES users(id) ON DELETE SET NULL,

            CONSTRAINT uq_section_lock_active UNIQUE (section_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_section_locks_expiry ON section_locks(expires_at)"
    )
    op.execute(
        "CREATE INDEX idx_section_locks_user ON section_locks(held_by)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS section_locks")
    op.execute("DROP TABLE IF EXISTS attachments")
    op.execute("DROP TABLE IF EXISTS work_item_tags")
    op.execute("DROP TABLE IF EXISTS tags")
