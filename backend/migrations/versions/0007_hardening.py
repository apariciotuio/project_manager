"""EP-00 post-review hardening — DB-level security, index, and constraint fixes.

Revision ID: 0007_hardening
Revises: 0006_oauth_states
Create Date: 2026-04-15

Changes:
  11. Replace audit_events RULEs with BEFORE triggers (rules are silent no-ops; triggers raise)
  12. audit_events FKs actor_id + workspace_id → ON DELETE SET NULL
  13. workspaces.created_by → ON DELETE RESTRICT (explicit, was implicit)
  14. Partial unique index: one active default membership per user
  15. Email case-insensitive uniqueness via functional index on lower(email)
  + oauth_states state/verifier columns → varchar(128) length cap
  + oauth_states new columns: return_to TEXT, last_chosen_workspace_id UUID
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_hardening"
down_revision = "0006_oauth_states"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 11. Replace audit_events RULEs with BEFORE triggers
    # -------------------------------------------------------------------------
    op.execute("DROP RULE IF EXISTS no_update_audit ON audit_events")
    op.execute("DROP RULE IF EXISTS no_delete_audit ON audit_events")

    op.execute("""
        CREATE OR REPLACE FUNCTION audit_events_block_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_events is append-only (attempted %)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER audit_events_no_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_mutation()
    """)

    op.execute("""
        CREATE TRIGGER audit_events_no_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_block_mutation()
    """)

    # -------------------------------------------------------------------------
    # 12. audit_events FKs → ON DELETE SET NULL
    # -------------------------------------------------------------------------
    op.drop_constraint("audit_events_actor_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_actor_id_fkey",
        "audit_events",
        "users",
        ["actor_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_constraint("audit_events_workspace_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_workspace_id_fkey",
        "audit_events",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # -------------------------------------------------------------------------
    # 13. workspaces.created_by → ON DELETE RESTRICT (explicit)
    # -------------------------------------------------------------------------
    op.drop_constraint("workspaces_created_by_fkey", "workspaces", type_="foreignkey")
    op.create_foreign_key(
        "workspaces_created_by_fkey",
        "workspaces",
        "users",
        ["created_by"],
        ["id"],
        ondelete="RESTRICT",
    )

    # -------------------------------------------------------------------------
    # 14. Partial unique: one active default membership per user
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE UNIQUE INDEX uq_default_active_membership_per_user
        ON workspace_memberships (user_id)
        WHERE is_default AND state = 'active'
    """)

    # -------------------------------------------------------------------------
    # 15. Email case-insensitive uniqueness via functional index
    # -------------------------------------------------------------------------
    # Drop case-sensitive unique constraint from ORM (declared as unique=True on column)
    op.drop_constraint("users_email_key", "users", type_="unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))"
    )

    # -------------------------------------------------------------------------
    # oauth_states: length caps + new columns
    # -------------------------------------------------------------------------
    op.alter_column("oauth_states", "state", type_=sa.String(128), existing_nullable=False)
    op.alter_column("oauth_states", "verifier", type_=sa.String(128), existing_nullable=False)
    op.add_column("oauth_states", sa.Column("return_to", sa.Text(), nullable=True))
    op.add_column(
        "oauth_states",
        sa.Column("last_chosen_workspace_id", sa.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    # oauth_states: remove new columns, restore text type
    op.drop_column("oauth_states", "last_chosen_workspace_id")
    op.drop_column("oauth_states", "return_to")
    op.alter_column("oauth_states", "verifier", type_=sa.Text(), existing_nullable=False)
    op.alter_column("oauth_states", "state", type_=sa.Text(), existing_nullable=False)

    # 15. Restore case-sensitive unique
    op.execute("DROP INDEX IF EXISTS uq_users_email_lower")
    op.create_unique_constraint("users_email_key", "users", ["email"])

    # 14. Drop partial unique index
    op.execute("DROP INDEX IF EXISTS uq_default_active_membership_per_user")

    # 13. Restore workspaces.created_by FK without explicit RESTRICT
    op.drop_constraint("workspaces_created_by_fkey", "workspaces", type_="foreignkey")
    op.create_foreign_key(
        "workspaces_created_by_fkey",
        "workspaces",
        "users",
        ["created_by"],
        ["id"],
    )

    # 12. Restore audit_events FKs without ON DELETE
    op.drop_constraint("audit_events_workspace_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_workspace_id_fkey",
        "audit_events",
        "workspaces",
        ["workspace_id"],
        ["id"],
    )

    op.drop_constraint("audit_events_actor_id_fkey", "audit_events", type_="foreignkey")
    op.create_foreign_key(
        "audit_events_actor_id_fkey",
        "audit_events",
        "users",
        ["actor_id"],
        ["id"],
    )

    # 11. Restore RULEs, drop triggers
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_delete ON audit_events")
    op.execute("DROP TRIGGER IF EXISTS audit_events_no_update ON audit_events")
    op.execute("DROP FUNCTION IF EXISTS audit_events_block_mutation()")

    op.execute("CREATE RULE no_update_audit AS ON UPDATE TO audit_events DO INSTEAD NOTHING")
    op.execute("CREATE RULE no_delete_audit AS ON DELETE TO audit_events DO INSTEAD NOTHING")
