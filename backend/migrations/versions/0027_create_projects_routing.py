"""EP-10 — projects + routing_rules + integration_configs.

Revision ID: 0027_projects_routing
Revises: 0026_saved_searches
Create Date: 2026-04-16

- projects: workspace-scoped container for work items (work_items.project_id
  existed as a bare UUID; this adds the actual table + FK)
- routing_rules: admin-defined suggestions for team / owner / validators
- integration_configs: Fernet-encrypted Jira (and future) credentials

integration_configs.encrypted_credentials is TEXT holding a Fernet token. The
key rotation runbook lives in ops docs (TBD).
"""
from __future__ import annotations

from alembic import op

revision = "0027_projects_routing"
down_revision = "0026_saved_searches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE projects (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id  UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name          VARCHAR(255) NOT NULL,
            description   TEXT,
            deleted_at    TIMESTAMPTZ,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by    UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX idx_projects_workspace_active_name "
        "ON projects(workspace_id, name) WHERE deleted_at IS NULL"
    )
    op.execute(
        "CREATE INDEX idx_projects_workspace_active "
        "ON projects(workspace_id) WHERE deleted_at IS NULL"
    )

    op.execute("""
        CREATE TABLE routing_rules (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
            work_item_type  VARCHAR(32) NOT NULL,
            suggested_team_id   UUID REFERENCES teams(id) ON DELETE SET NULL,
            suggested_owner_id  UUID REFERENCES users(id) ON DELETE SET NULL,
            suggested_validators JSONB NOT NULL DEFAULT '[]'::jsonb,
            priority        INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by      UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_routing_rules_match "
        "ON routing_rules(workspace_id, project_id, work_item_type, priority DESC)"
    )

    op.execute("""
        CREATE TABLE integration_configs (
            id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id           UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id             UUID REFERENCES projects(id) ON DELETE SET NULL,
            integration_type       VARCHAR(32) NOT NULL,
            encrypted_credentials  TEXT NOT NULL,
            mapping                JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_active              BOOLEAN NOT NULL DEFAULT true,
            created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by             UUID NOT NULL REFERENCES users(id),

            CONSTRAINT integration_configs_type_valid
                CHECK (integration_type IN ('jira', 'github', 'slack', 'other'))
        )
    """)
    op.execute(
        "CREATE INDEX idx_integration_configs_workspace "
        "ON integration_configs(workspace_id, integration_type) WHERE is_active = true"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_configs")
    op.execute("DROP TABLE IF EXISTS routing_rules")
    op.execute("DROP TABLE IF EXISTS projects")
