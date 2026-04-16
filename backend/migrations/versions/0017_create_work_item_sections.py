"""EP-04 Phase 1a — create work_item_sections table.

Revision ID: 0017_create_work_item_sections
Revises: 0016_create_gap_findings
Create Date: 2026-04-16

One row per section per work item. Sections are typed (see SectionType enum in
domain/models/section_type.py) and ordered by display_order.

generation_source: 'llm' | 'manual' | 'revert'.
version is bumped on every save (mirrors work_item_section_versions row).

UNIQUE(work_item_id, section_type) enforces a single row per section type per
work item.

Composite index idx_wis_completeness (per db_review.md IDX-6) covers the
CompletenessService filter by (work_item_id, is_required) without hitting the
heap for section_type.
"""
from __future__ import annotations

from alembic import op

revision = "0017_work_item_sections"
down_revision = "0016_gap_findings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE work_item_sections (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id      UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            section_type      VARCHAR(64) NOT NULL,
            content           TEXT NOT NULL DEFAULT '',
            display_order     SMALLINT NOT NULL,
            is_required       BOOLEAN NOT NULL DEFAULT FALSE,
            generation_source VARCHAR(16) NOT NULL DEFAULT 'llm',
            version           INTEGER NOT NULL DEFAULT 1,
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by        UUID NOT NULL REFERENCES users(id),
            updated_by        UUID NOT NULL REFERENCES users(id),

            CONSTRAINT uq_work_item_section_type UNIQUE (work_item_id, section_type),
            CONSTRAINT work_item_sections_generation_source_valid
                CHECK (generation_source IN ('llm', 'manual', 'revert'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_work_item_sections_work_item_id
            ON work_item_sections(work_item_id)
    """)

    op.execute("""
        CREATE INDEX idx_wis_completeness
            ON work_item_sections(work_item_id, is_required, section_type)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_wis_completeness")
    op.execute("DROP INDEX IF EXISTS idx_work_item_sections_work_item_id")
    op.execute("DROP TABLE IF EXISTS work_item_sections")
