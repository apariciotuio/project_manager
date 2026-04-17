"""EP-10 — create validation_rule_templates table.

Revision ID: 0111_ep10_validation_rule_templates
Revises: 0110_ep10_routing_rules_active
Create Date: 2026-04-17

When a work item is created, if templates exist matching
(workspace_id, work_item_type), validation_requirements rows
are seeded for it. This migration creates the source table.
"""
from __future__ import annotations

from alembic import op

revision = "0111_ep10_validation_tpl"
down_revision = "0110_ep10_routing_rules_active"
branch_labels = None
depends_on = None

_REQUIREMENT_TYPES = (
    "'section_content','reviewer_approval','validator_approval','custom'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE validation_rule_templates (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id        UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            name                VARCHAR(80) NOT NULL,
            work_item_type      VARCHAR(40),
            requirement_type    VARCHAR(40) NOT NULL
                CHECK (requirement_type IN ({_REQUIREMENT_TYPES})),
            default_dimension   VARCHAR(100),
            default_description TEXT,
            is_mandatory        BOOLEAN NOT NULL,
            active              BOOLEAN NOT NULL DEFAULT true,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX idx_vrt_workspace_type "
        "ON validation_rule_templates(workspace_id, work_item_type) "
        "WHERE active = true"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS validation_rule_templates")
