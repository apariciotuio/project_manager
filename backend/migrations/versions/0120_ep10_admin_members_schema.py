"""EP-10 — Admin members: capabilities + context_labels + invitations + context_presets.

Revision ID: 0120_ep10_admin_members_schema
Revises: 0119_lock_unlock_requests
Create Date: 2026-04-18

Groups 0 (partial) + partial Group 1 schema:
  1. Add capabilities text[] + context_labels text[] to workspace_memberships
  2. GIN index on capabilities
  3. Create invitations table
  4. Create context_presets table (workspace-level LLM context snippets)
  5. RLS on invitations + context_presets
"""
from __future__ import annotations

from alembic import op

revision = "0120_ep10_admin_members_schema"
down_revision = "0119_lock_unlock_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen alembic_version.version_num — later revision IDs exceed the default
    # VARCHAR(32) that Alembic creates. Done here (earliest long-named migration
    # in the chain) so asyncpg does not cache a prepared UPDATE against the old
    # column type when stamping 0121+.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    # ------------------------------------------------------------------
    # 1. capabilities + context_labels on workspace_memberships
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE workspace_memberships
            ADD COLUMN IF NOT EXISTS capabilities TEXT[] NOT NULL DEFAULT '{}',
            ADD COLUMN IF NOT EXISTS context_labels TEXT[] NOT NULL DEFAULT '{}'
    """)

    # GIN index for capability queries (e.g. WHERE 'invite_members' = ANY(capabilities))
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_wm_capabilities_gin
            ON workspace_memberships USING gin(capabilities)
    """)

    # ------------------------------------------------------------------
    # 2. invitations table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE invitations (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            email            TEXT NOT NULL,
            token_hash       TEXT NOT NULL UNIQUE,
            state            TEXT NOT NULL DEFAULT 'invited'
                                 CHECK (state IN ('invited', 'accepted', 'expired', 'revoked')),
            context_labels   TEXT[] NOT NULL DEFAULT '{}',
            team_ids         UUID[] NOT NULL DEFAULT '{}',
            initial_capabilities TEXT[] NOT NULL DEFAULT '{}',
            created_by       UUID NOT NULL REFERENCES users(id),
            expires_at       TIMESTAMPTZ NOT NULL,
            accepted_at      TIMESTAMPTZ,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("""
        CREATE INDEX idx_invitations_workspace_email
            ON invitations(workspace_id, email)
    """)
    op.execute("""
        CREATE INDEX idx_invitations_token_hash ON invitations(token_hash)
    """)
    op.execute("""
        CREATE INDEX idx_invitations_expires_at ON invitations(expires_at)
            WHERE state = 'invited'
    """)

    # RLS on invitations
    op.execute("ALTER TABLE invitations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY invitations_workspace_isolation ON invitations
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    # ------------------------------------------------------------------
    # 3. context_presets table
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE context_presets (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name         TEXT NOT NULL,
            description  TEXT,
            sources      JSONB NOT NULL DEFAULT '[]',
            deleted_at   TIMESTAMPTZ,
            created_by   UUID NOT NULL REFERENCES users(id),
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(workspace_id, name)
        )
    """)
    op.execute("""
        CREATE INDEX idx_context_presets_workspace
            ON context_presets(workspace_id)
            WHERE deleted_at IS NULL
    """)

    # RLS on context_presets
    op.execute("ALTER TABLE context_presets ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY context_presets_workspace_isolation ON context_presets
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS context_presets CASCADE")
    op.execute("DROP TABLE IF EXISTS invitations CASCADE")
    op.execute("""
        ALTER TABLE workspace_memberships
            DROP COLUMN IF EXISTS capabilities,
            DROP COLUMN IF EXISTS context_labels
    """)
