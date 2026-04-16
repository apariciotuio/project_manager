"""EP-02 Phase 1c — create templates table and add FK on work_items.template_id.

Revision ID: 0013_create_templates
Revises: 0012_create_work_item_drafts
Create Date: 2026-04-15

Templates use English type values matching WorkItemType enum:
    idea, bug, enhancement, task, initiative, spike, business_change, requirement

Two mutual-exclusion rules enforced by DB:
  1. is_system=TRUE → workspace_id IS NULL
  2. One workspace template per type per workspace (unique partial index)
  3. One system template per type (unique partial index)

After creating templates, we add the FK from work_items.template_id.
"""
from __future__ import annotations

from alembic import op

revision = "0013_create_templates"
down_revision = "0012_create_work_item_drafts"
branch_labels = None
depends_on = None

_VALID_TYPES = (
    "'idea','bug','enhancement','task','initiative','spike','business_change','requirement'"
)


def upgrade() -> None:
    op.execute(f"""
        CREATE TABLE templates (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id    UUID REFERENCES workspaces(id) ON DELETE CASCADE,
            type            VARCHAR(50) NOT NULL,
            name            VARCHAR(255) NOT NULL,
            content         TEXT NOT NULL,
            is_system       BOOLEAN NOT NULL DEFAULT FALSE,
            created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT templates_type_valid CHECK (type IN ({_VALID_TYPES})),
            CONSTRAINT templates_content_length CHECK (char_length(content) <= 50000),
            CONSTRAINT templates_system_no_workspace CHECK (
                NOT (is_system = TRUE AND workspace_id IS NOT NULL)
            )
        )
    """)

    # One workspace template per type per workspace
    op.execute("""
        CREATE UNIQUE INDEX idx_templates_workspace_type
            ON templates(workspace_id, type)
            WHERE workspace_id IS NOT NULL
    """)

    # One system template per type
    op.execute("""
        CREATE UNIQUE INDEX idx_templates_system_type
            ON templates(type)
            WHERE is_system = TRUE
    """)

    op.execute("""
        CREATE INDEX idx_templates_workspace
            ON templates(workspace_id)
            WHERE workspace_id IS NOT NULL
    """)

    # Now add the FK and partial index on work_items.template_id
    op.execute("""
        ALTER TABLE work_items
            ADD CONSTRAINT fk_work_items_template_id
            FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE SET NULL
    """)

    op.execute("""
        CREATE INDEX idx_work_items_template
            ON work_items(template_id)
            WHERE template_id IS NOT NULL AND deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_work_items_template")
    op.execute("""
        ALTER TABLE work_items
            DROP CONSTRAINT IF EXISTS fk_work_items_template_id
    """)
    op.execute("DROP TABLE IF EXISTS templates")
