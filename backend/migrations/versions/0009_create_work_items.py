"""EP-01 Phase 2 — create work_items, state_transitions, ownership_history.

Revision ID: 0009_create_work_items
Revises: 0008_indexes
Create Date: 2026-04-15

All three tables in a single migration for atomicity. RLS enabled on all three.
Append-only triggers on state_transitions and ownership_history (same pattern as
audit_events in 0007_hardening).

Notes:
  - work_items.project_id has NO FK yet.
    TODO(EP-10): add FK to projects(id) once projects table exists.
  - work_items.parent_work_item_id ON DELETE SET NULL — orphaned children become roots.
    TODO(EP-14): add cycle-prevention trigger / DB-level check.
  - work_items type enum excludes milestone/story.
    TODO(EP-14): ALTER TABLE work_items DROP CONSTRAINT work_items_type_valid,
                 ADD CONSTRAINT work_items_type_valid CHECK (..., 'milestone', 'story').
"""

from __future__ import annotations

from alembic import op

revision = "0009_create_work_items"
down_revision = "0008_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # work_items
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE work_items (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
            -- TODO(EP-10): add FK REFERENCES projects(id) once projects table exists
            project_id              UUID NOT NULL,
            type                    VARCHAR(32) NOT NULL,
            state                   VARCHAR(32) NOT NULL DEFAULT 'draft',
            title                   VARCHAR(255) NOT NULL,
            description             TEXT NULL,
            original_input          TEXT NULL,
            priority                VARCHAR(16) NULL,
            due_date                DATE NULL,
            tags                    TEXT[] NOT NULL DEFAULT '{}',
            completeness_score      SMALLINT NOT NULL DEFAULT 0,
            parent_work_item_id     UUID NULL REFERENCES work_items(id) ON DELETE SET NULL,
            -- TODO(EP-14): add cycle-prevention trigger
            materialized_path       TEXT NOT NULL DEFAULT '',
            attachment_count        INTEGER NOT NULL DEFAULT 0,
            owner_id                UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            creator_id              UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            has_override            BOOLEAN NOT NULL DEFAULT FALSE,
            override_justification  TEXT NULL,
            owner_suspended_flag    BOOLEAN NOT NULL DEFAULT FALSE,
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at              TIMESTAMPTZ NULL,
            exported_at             TIMESTAMPTZ NULL,
            export_reference        TEXT NULL,

            CONSTRAINT work_items_type_valid CHECK (type IN (
                'idea','bug','enhancement','task','initiative','spike','business_change','requirement'
            )),
            CONSTRAINT work_items_state_valid CHECK (state IN (
                'draft','in_clarification','in_review','changes_requested',
                'partially_validated','ready','exported'
            )),
            CONSTRAINT work_items_title_length CHECK (
                char_length(trim(title)) BETWEEN 3 AND 255
            ),
            CONSTRAINT work_items_priority_valid CHECK (
                priority IS NULL OR priority IN ('low','medium','high','critical')
            ),
            CONSTRAINT work_items_completeness_range CHECK (
                completeness_score BETWEEN 0 AND 100
            ),
            CONSTRAINT work_items_attachment_count_nonneg CHECK (
                attachment_count >= 0
            )
        )
    """)

    op.execute("""
        CREATE INDEX idx_work_items_workspace_state
            ON work_items(workspace_id, state)
    """)
    op.execute("""
        CREATE INDEX idx_work_items_active
            ON work_items(workspace_id, updated_at DESC)
            WHERE deleted_at IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_work_items_owner
            ON work_items(owner_id)
    """)
    op.execute("""
        CREATE INDEX idx_work_items_parent
            ON work_items(parent_work_item_id)
    """)
    op.execute("""
        CREATE INDEX idx_work_items_tags
            ON work_items USING GIN(tags)
    """)

    # RLS — default-deny; superusers bypass by default (prod runs as non-superuser app role)
    op.execute("ALTER TABLE work_items ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY work_items_workspace_isolation ON work_items
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    # ------------------------------------------------------------------
    # state_transitions (append-only audit)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE state_transitions (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id            UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            workspace_id            UUID NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
            from_state              VARCHAR(32) NULL,
            to_state                VARCHAR(32) NOT NULL,
            actor_id                UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            triggered_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason                  TEXT NULL,
            is_override             BOOLEAN NOT NULL DEFAULT FALSE,
            override_justification  TEXT NULL,

            CONSTRAINT state_transitions_from_state_valid CHECK (
                from_state IS NULL OR from_state IN (
                    'draft','in_clarification','in_review','changes_requested',
                    'partially_validated','ready','exported'
                )
            ),
            CONSTRAINT state_transitions_to_state_valid CHECK (to_state IN (
                'draft','in_clarification','in_review','changes_requested',
                'partially_validated','ready','exported'
            ))
        )
    """)

    op.execute("""
        CREATE INDEX idx_state_transitions_item
            ON state_transitions(work_item_id, triggered_at DESC)
    """)

    op.execute("ALTER TABLE state_transitions ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY state_transitions_workspace_isolation ON state_transitions
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    # Append-only trigger (same pattern as audit_events in 0007_hardening)
    op.execute("""
        CREATE OR REPLACE FUNCTION state_transitions_block_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'state_transitions is append-only (attempted %)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER state_transitions_no_update
        BEFORE UPDATE ON state_transitions
        FOR EACH ROW EXECUTE FUNCTION state_transitions_block_mutation()
    """)
    op.execute("""
        CREATE TRIGGER state_transitions_no_delete
        BEFORE DELETE ON state_transitions
        FOR EACH ROW EXECUTE FUNCTION state_transitions_block_mutation()
    """)

    # ------------------------------------------------------------------
    # ownership_history (append-only audit)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE ownership_history (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id        UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            workspace_id        UUID NOT NULL REFERENCES workspaces(id) ON DELETE RESTRICT,
            previous_owner_id   UUID NULL REFERENCES users(id) ON DELETE RESTRICT,
            new_owner_id        UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            changed_by          UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            changed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason              TEXT NULL
        )
    """)

    op.execute("""
        CREATE INDEX idx_ownership_history_item
            ON ownership_history(work_item_id, changed_at DESC)
    """)

    op.execute("ALTER TABLE ownership_history ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ownership_history_workspace_isolation ON ownership_history
            USING (workspace_id::text = current_setting('app.current_workspace', true))
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION ownership_history_block_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'ownership_history is append-only (attempted %)', TG_OP;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER ownership_history_no_update
        BEFORE UPDATE ON ownership_history
        FOR EACH ROW EXECUTE FUNCTION ownership_history_block_mutation()
    """)
    op.execute("""
        CREATE TRIGGER ownership_history_no_delete
        BEFORE DELETE ON ownership_history
        FOR EACH ROW EXECUTE FUNCTION ownership_history_block_mutation()
    """)


def downgrade() -> None:
    # Drop in reverse dependency order

    # ownership_history
    op.execute("DROP TRIGGER IF EXISTS ownership_history_no_delete ON ownership_history")
    op.execute("DROP TRIGGER IF EXISTS ownership_history_no_update ON ownership_history")
    op.execute("DROP FUNCTION IF EXISTS ownership_history_block_mutation()")
    op.execute("DROP POLICY IF EXISTS ownership_history_workspace_isolation ON ownership_history")
    op.execute("DROP INDEX IF EXISTS idx_ownership_history_item")
    op.execute("DROP TABLE IF EXISTS ownership_history")

    # state_transitions
    op.execute("DROP TRIGGER IF EXISTS state_transitions_no_delete ON state_transitions")
    op.execute("DROP TRIGGER IF EXISTS state_transitions_no_update ON state_transitions")
    op.execute("DROP FUNCTION IF EXISTS state_transitions_block_mutation()")
    op.execute("DROP POLICY IF EXISTS state_transitions_workspace_isolation ON state_transitions")
    op.execute("DROP INDEX IF EXISTS idx_state_transitions_item")
    op.execute("DROP TABLE IF EXISTS state_transitions")

    # work_items
    op.execute("DROP POLICY IF EXISTS work_items_workspace_isolation ON work_items")
    op.execute("DROP INDEX IF EXISTS idx_work_items_tags")
    op.execute("DROP INDEX IF EXISTS idx_work_items_parent")
    op.execute("DROP INDEX IF EXISTS idx_work_items_owner")
    op.execute("DROP INDEX IF EXISTS idx_work_items_active")
    op.execute("DROP INDEX IF EXISTS idx_work_items_workspace_state")
    op.execute("DROP TABLE IF EXISTS work_items")
