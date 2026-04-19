"""EP-18 — Create mcp_tokens table + indexes.

Revision ID: 0123_ep18_mcp_tokens
Revises: 0122_ep22_primer_sent_at
Create Date: 2026-04-18

Changes:
  1. CREATE TABLE mcp_tokens
  2. Partial index idx_mcp_tokens_ws_user_active
  3. Partial index idx_mcp_tokens_expires_active
  4. UNIQUE index on lookup_key_hmac
"""
from __future__ import annotations

from alembic import op

revision = "0123_ep18_mcp_tokens"
down_revision = "0122_ep22_primer_sent_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS mcp_tokens (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL,
            user_id          UUID NOT NULL,
            name             VARCHAR(200) NOT NULL,
            token_hash_argon2 TEXT NOT NULL,
            lookup_key_hmac  BYTEA NOT NULL,
            scopes           TEXT[] NOT NULL DEFAULT '{}',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at       TIMESTAMPTZ NOT NULL,
            last_used_at     TIMESTAMPTZ NULL,
            revoked_at       TIMESTAMPTZ NULL,
            rotated_from     UUID NULL
        )
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_tokens_lookup_key
            ON mcp_tokens (lookup_key_hmac)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mcp_tokens_ws_user_active
            ON mcp_tokens (workspace_id, user_id)
            WHERE revoked_at IS NULL
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mcp_tokens_expires_active
            ON mcp_tokens (expires_at)
            WHERE revoked_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mcp_tokens_expires_active")
    op.execute("DROP INDEX IF EXISTS idx_mcp_tokens_ws_user_active")
    op.execute("DROP INDEX IF EXISTS uq_mcp_tokens_lookup_key")
    op.execute("DROP TABLE IF EXISTS mcp_tokens")
