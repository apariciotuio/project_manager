"""EP-03 Phase 1c — create gap_findings table.

Revision ID: 0016_create_gap_findings
Revises: 0015_create_assistant_suggestions
Create Date: 2026-04-16

Stores gap analysis findings for work items. A finding can originate from a
local rule engine (source='rule') or from a Dundun LLM analysis
(source='dundun').

Rows are never physically deleted. invalidated_at is set when a work item is
updated and old findings are superseded by a new analysis run.

The partial index idx_gap_findings_active on (work_item_id) WHERE
invalidated_at IS NULL is the primary access pattern for "current findings".
"""
from __future__ import annotations

from alembic import op

revision = "0016_gap_findings"
down_revision = "0015_assistant_suggestions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE gap_findings (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id        UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            source              VARCHAR(20) NOT NULL,
            severity            VARCHAR(20) NOT NULL,
            dimension           VARCHAR(100) NOT NULL,
            message             TEXT NOT NULL,
            dundun_request_id   TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            invalidated_at      TIMESTAMPTZ,

            CONSTRAINT gap_findings_source_valid
                CHECK (source IN ('rule', 'dundun')),
            CONSTRAINT gap_findings_severity_valid
                CHECK (severity IN ('blocking', 'warning', 'info'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_gap_findings_work_item
            ON gap_findings(work_item_id, source, severity)
    """)

    op.execute("""
        CREATE INDEX idx_gap_findings_active
            ON gap_findings(work_item_id)
            WHERE invalidated_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_gap_findings_active")
    op.execute("DROP INDEX IF EXISTS idx_gap_findings_work_item")
    op.execute("DROP TABLE IF EXISTS gap_findings")
