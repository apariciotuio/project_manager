"""EP-10 — Admin rules, jira config, support tables.

Revision ID: 0121_ep10_admin_rules_jira_support
Revises: 0120_ep10_admin_members_schema
Create Date: 2026-04-18

Creates:
  1. validation_rules table (workspace + project scoped)
  2. routing_rules_v2 is not needed — routing_rules table already exists (0110)
  3. jira_configs table
  4. jira_project_mappings table
  5. RLS on new tables
"""
from __future__ import annotations

from alembic import op

revision = "0121_ep10_admin_rules_jira_support"
down_revision = "0120_ep10_admin_members_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen alembic_version.version_num — this revision ID exceeds the default
    # VARCHAR(32) that Alembic creates. Must run before Alembic stamps the new
    # version at the end of the transaction.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    # ------------------------------------------------------------------
    # 1. validation_rules
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE validation_rules (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id       UUID REFERENCES projects(id) ON DELETE CASCADE,
            work_item_type   TEXT NOT NULL,
            validation_type  TEXT NOT NULL,
            enforcement      TEXT NOT NULL DEFAULT 'recommended'
                                 CHECK (enforcement IN ('required', 'recommended', 'blocked_override')),
            active           BOOLEAN NOT NULL DEFAULT true,
            created_by       UUID NOT NULL REFERENCES users(id),
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Partial UNIQUE: prevents duplicate workspace-scope rules (ALG-7 from design)
    op.execute("""
        CREATE UNIQUE INDEX uq_validation_rules_workspace_scope
            ON validation_rules(workspace_id, work_item_type, validation_type)
            WHERE project_id IS NULL AND active = true
    """)

    # Partial UNIQUE: prevents duplicate project-scope rules
    op.execute("""
        CREATE UNIQUE INDEX uq_validation_rules_project_scope
            ON validation_rules(workspace_id, project_id, work_item_type, validation_type)
            WHERE project_id IS NOT NULL AND active = true
    """)

    # Lookup index
    op.execute("""
        CREATE INDEX idx_validation_rules_lookup
            ON validation_rules(workspace_id, work_item_type, validation_type)
            WHERE active = true
    """)

    # RLS
    op.execute("ALTER TABLE validation_rules ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY validation_rules_workspace_isolation ON validation_rules
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    # ------------------------------------------------------------------
    # 2. jira_configs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE jira_configs (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            project_id              UUID REFERENCES projects(id) ON DELETE SET NULL,
            base_url                TEXT NOT NULL,
            auth_type               TEXT NOT NULL DEFAULT 'basic'
                                        CHECK (auth_type IN ('basic', 'oauth2')),
            credentials_ref         TEXT NOT NULL,
            state                   TEXT NOT NULL DEFAULT 'active'
                                        CHECK (state IN ('active', 'disabled', 'error')),
            last_health_check_status TEXT CHECK (
                                        last_health_check_status IS NULL OR
                                        last_health_check_status IN ('ok', 'auth_failure', 'unreachable')
                                    ),
            last_health_check_at    TIMESTAMPTZ,
            consecutive_failures    INTEGER NOT NULL DEFAULT 0,
            created_by              UUID NOT NULL REFERENCES users(id),
            created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(workspace_id, project_id)
        )
    """)

    op.execute("""
        CREATE INDEX idx_jira_configs_workspace ON jira_configs(workspace_id)
    """)

    # RLS
    op.execute("ALTER TABLE jira_configs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY jira_configs_workspace_isolation ON jira_configs
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    # ------------------------------------------------------------------
    # 3. jira_project_mappings
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE jira_project_mappings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            jira_config_id    UUID NOT NULL REFERENCES jira_configs(id) ON DELETE CASCADE,
            workspace_id      UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            jira_project_key  TEXT NOT NULL,
            local_project_id  UUID REFERENCES projects(id) ON DELETE SET NULL,
            type_mappings     JSONB NOT NULL DEFAULT '{}',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(jira_config_id, jira_project_key)
        )
    """)

    op.execute("""
        CREATE INDEX idx_jira_mappings_config ON jira_project_mappings(jira_config_id)
    """)

    # RLS
    op.execute("ALTER TABLE jira_project_mappings ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY jira_project_mappings_workspace_isolation ON jira_project_mappings
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS jira_project_mappings CASCADE")
    op.execute("DROP TABLE IF EXISTS jira_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS validation_rules CASCADE")
