"""EP-04 Phase 1b — create work_item_section_versions table.

Revision ID: 0018_create_work_item_section_versions
Revises: 0017_create_work_item_sections
Create Date: 2026-04-16

Append-only version log per section. Never UPDATE rows in this table. Enables
per-section diff and revert within the EP-04 UI.

Denormalized work_item_id + section_type make cross-section queries trivial.
revert_from_version is set when generation_source = 'revert'.
"""
from __future__ import annotations

from alembic import op

revision = "0018_section_versions"
down_revision = "0017_work_item_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE work_item_section_versions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            section_id          UUID NOT NULL REFERENCES work_item_sections(id) ON DELETE CASCADE,
            work_item_id        UUID NOT NULL,
            section_type        VARCHAR(64) NOT NULL,
            content             TEXT NOT NULL,
            version             INTEGER NOT NULL,
            generation_source   VARCHAR(16) NOT NULL,
            revert_from_version INTEGER,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by          UUID NOT NULL REFERENCES users(id),

            CONSTRAINT work_item_section_versions_generation_source_valid
                CHECK (generation_source IN ('llm', 'manual', 'revert'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_section_versions_section_id
            ON work_item_section_versions(section_id)
    """)

    op.execute("""
        CREATE INDEX idx_section_versions_work_item_id
            ON work_item_section_versions(work_item_id)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_section_versions_work_item_id")
    op.execute("DROP INDEX IF EXISTS idx_section_versions_section_id")
    op.execute("DROP TABLE IF EXISTS work_item_section_versions")
