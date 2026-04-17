"""EP-06 Phase 1 — fix review/validation schema gaps not covered by 0023.

Adds:
- workspace_id + description + is_active + created_by + created_at + updated_at to validation_requirements
- UNIQUE constraint on review_responses(review_request_id) — one response per request
- Content check constraint on review_responses
- Seed built-in validation rules (spec_review_complete, tech_review_complete)
- Gate index on validation_status for ReadyGateService hot path

Revision ID: 0060_ep06_review_schema_fixes
Revises: 0034_ep13_puppet_ingest_requests
Create Date: 2026-04-17
"""
from __future__ import annotations

from alembic import op

revision = "0060_ep06_review_schema_fixes"
down_revision = "0034_puppet_ingest_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # Extend validation_requirements with workspace scoping + metadata columns
    # ---------------------------------------------------------------------------
    op.execute("""
        ALTER TABLE validation_requirements
            ADD COLUMN IF NOT EXISTS workspace_id UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            ADD COLUMN IF NOT EXISTS description TEXT,
            ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
            ADD COLUMN IF NOT EXISTS created_by UUID REFERENCES users(id),
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ADD COLUMN IF NOT EXISTS applies_to_arr TEXT[] NOT NULL DEFAULT '{}'
    """)

    # Unique index for workspace-scoped rules (NULL workspace_id = built-in global)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_validation_requirements_ws_rule
        ON validation_requirements (workspace_id, rule_id)
        WHERE workspace_id IS NOT NULL
    """)

    # ---------------------------------------------------------------------------
    # Enforce one response per request (DB-level backstop for the service check)
    # ---------------------------------------------------------------------------
    # PostgreSQL does not support ADD CONSTRAINT IF NOT EXISTS; use DO block for idempotency.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_one_response_per_request'
            ) THEN
                ALTER TABLE review_responses
                    ADD CONSTRAINT uq_one_response_per_request UNIQUE (review_request_id);
            END IF;
        END $$
    """)

    # Content required when decision != approved — DB-level guard
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'review_responses_content_required_when_not_approved'
            ) THEN
                ALTER TABLE review_responses
                    ADD CONSTRAINT review_responses_content_required_when_not_approved
                    CHECK (decision = 'approved' OR content IS NOT NULL);
            END IF;
        END $$
    """)

    # ---------------------------------------------------------------------------
    # Gate index for ReadyGateService — filters (work_item_id, status) where
    # status NOT IN ('passed', 'obsolete'). Partial keeps it small & fast.
    # ---------------------------------------------------------------------------
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_validation_status_gate
        ON validation_status (work_item_id, status)
        WHERE status NOT IN ('passed', 'obsolete')
    """)

    # ---------------------------------------------------------------------------
    # Seed built-in validation rules (workspace_id IS NULL = global defaults)
    # ---------------------------------------------------------------------------
    op.execute("""
        INSERT INTO validation_requirements (rule_id, label, required, applies_to, applies_to_arr, is_active)
        VALUES
            ('spec_review_complete',  'Spec review complete',  TRUE,  '', '{}', TRUE),
            ('tech_review_complete',  'Tech review complete',  FALSE, '', '{}', TRUE)
        ON CONFLICT (rule_id) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM validation_requirements WHERE rule_id IN ('spec_review_complete', 'tech_review_complete')")
    op.execute("DROP INDEX IF EXISTS idx_validation_status_gate")
    op.execute("""
        ALTER TABLE review_responses
            DROP CONSTRAINT IF EXISTS review_responses_content_required_when_not_approved,
            DROP CONSTRAINT IF EXISTS uq_one_response_per_request
    """)
    op.execute("DROP INDEX IF EXISTS idx_validation_requirements_ws_rule")
    op.execute("""
        ALTER TABLE validation_requirements
            DROP COLUMN IF EXISTS applies_to_arr,
            DROP COLUMN IF EXISTS updated_at,
            DROP COLUMN IF EXISTS created_at,
            DROP COLUMN IF EXISTS created_by,
            DROP COLUMN IF EXISTS is_active,
            DROP COLUMN IF EXISTS description,
            DROP COLUMN IF EXISTS workspace_id
    """)
