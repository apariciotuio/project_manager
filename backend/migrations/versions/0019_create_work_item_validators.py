"""EP-04 Phase 1c — create work_item_validators table.

Revision ID: 0019_create_work_item_validators
Revises: 0018_create_work_item_section_versions
Create Date: 2026-04-16

Validator assignments per work item. Each (work_item_id, role) pair is unique.
responded_at is set when the validator's status changes from 'pending' to any
other state.

Validator rules live in DB (EP-06 validation_requirements), not in YAML.
"""
from __future__ import annotations

from alembic import op

revision = "0019_work_item_validators"
down_revision = "0018_section_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE work_item_validators (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
            role            VARCHAR(64) NOT NULL,
            status          VARCHAR(32) NOT NULL DEFAULT 'pending',
            assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            assigned_by     UUID NOT NULL REFERENCES users(id),
            responded_at    TIMESTAMPTZ,

            CONSTRAINT uq_work_item_validator UNIQUE (work_item_id, role),
            CONSTRAINT work_item_validators_status_valid
                CHECK (status IN ('pending', 'approved', 'changes_requested', 'declined'))
        )
    """)

    op.execute("""
        CREATE INDEX idx_work_item_validators_work_item
            ON work_item_validators(work_item_id, status)
    """)

    op.execute("""
        CREATE INDEX idx_work_item_validators_user_pending
            ON work_item_validators(user_id)
            WHERE status = 'pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_work_item_validators_user_pending")
    op.execute("DROP INDEX IF EXISTS idx_work_item_validators_work_item")
    op.execute("DROP TABLE IF EXISTS work_item_validators")
