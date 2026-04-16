"""EP-08 — teams + team_memberships + notifications + review_requests.team_id FK.

Revision ID: 0025_teams_notifications
Revises: 0024_ep07_versions_comments
Create Date: 2026-04-16

Adds the team surface (soft-delete via deleted_at), memberships, and the
notifications outbox. Also closes the deferred FK from EP-06's
review_requests.team_id to the newly created teams table.
"""
from __future__ import annotations

from alembic import op

revision = "0025_teams_notifications"
down_revision = "0024_ep07_versions_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE teams (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id         UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            name                 VARCHAR(255) NOT NULL,
            description          TEXT,
            can_receive_reviews  BOOLEAN NOT NULL DEFAULT false,
            deleted_at           TIMESTAMPTZ,
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by           UUID NOT NULL REFERENCES users(id)
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX idx_teams_workspace_active_name
        ON teams(workspace_id, name)
        WHERE deleted_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_teams_workspace_active
        ON teams(workspace_id)
        WHERE deleted_at IS NULL
    """)

    op.execute("""
        CREATE TABLE team_memberships (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            team_id      UUID NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            role         VARCHAR(20) NOT NULL DEFAULT 'member',
            joined_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            removed_at   TIMESTAMPTZ,

            CONSTRAINT team_memberships_role_valid CHECK (role IN ('member', 'lead')),
            CONSTRAINT uq_team_membership_active UNIQUE (team_id, user_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_team_memberships_user_active ON team_memberships"
        "(user_id) WHERE removed_at IS NULL"
    )

    op.execute("""
        CREATE TABLE notifications (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id     UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
            recipient_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type             VARCHAR(64) NOT NULL,
            state            VARCHAR(16) NOT NULL DEFAULT 'unread',
            actor_id         UUID REFERENCES users(id) ON DELETE SET NULL,
            subject_type     VARCHAR(32) NOT NULL,
            subject_id       UUID NOT NULL,
            deeplink         TEXT NOT NULL,
            quick_action     JSONB,
            extra            JSONB NOT NULL DEFAULT '{}'::jsonb,
            idempotency_key  TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            read_at          TIMESTAMPTZ,
            actioned_at      TIMESTAMPTZ,

            CONSTRAINT notifications_state_valid
                CHECK (state IN ('unread', 'read', 'actioned')),
            CONSTRAINT uq_notifications_idempotency
                UNIQUE (recipient_id, idempotency_key)
        )
    """)
    op.execute(
        "CREATE INDEX idx_notifications_recipient_unread ON notifications"
        "(recipient_id, created_at DESC) WHERE state = 'unread'"
    )
    op.execute(
        "CREATE INDEX idx_notifications_workspace ON notifications(workspace_id, created_at DESC)"
    )

    # Close the deferred FK from EP-06 review_requests.team_id -> teams.id.
    op.execute("""
        ALTER TABLE review_requests
        ADD CONSTRAINT review_requests_team_fk
            FOREIGN KEY (team_id)
            REFERENCES teams(id)
            ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute(
        "ALTER TABLE review_requests DROP CONSTRAINT IF EXISTS review_requests_team_fk"
    )
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS team_memberships")
    op.execute("DROP TABLE IF EXISTS teams")
