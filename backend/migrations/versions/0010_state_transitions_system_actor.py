"""EP-01 Phase 3 — drop FK + make actor_id nullable on state_transitions.

Revision ID: 0010_state_transitions_system_actor
Revises: 0009_create_work_items
Create Date: 2026-04-15

Rationale: the system actor (auto-revert on content change, creation events)
has no user row in the `users` table. Rather than polluting `users` with a
synthetic seed row, we drop the FK on `state_transitions.actor_id` and make
the column nullable. NULL actor_id = system-triggered transition.

Down: re-add the FK constraint (after updating any NULL rows to a known ID is
the caller's responsibility, but in test/dev we expect no NULLs unless the
system actor was exercised).
"""
from __future__ import annotations

from alembic import op

revision = "0010_system_actor"
down_revision = "0009_create_work_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the existing FK constraint on actor_id
    op.execute("""
        ALTER TABLE state_transitions
            DROP CONSTRAINT IF EXISTS state_transitions_actor_id_fkey
    """)
    # Make the column nullable
    op.execute("""
        ALTER TABLE state_transitions
            ALTER COLUMN actor_id DROP NOT NULL
    """)


def downgrade() -> None:
    # Nullify any system-actor rows before re-adding the FK (best-effort)
    # In practice downgrade is only used in test environments.
    op.execute("""
        DELETE FROM state_transitions WHERE actor_id IS NULL
    """)
    op.execute("""
        ALTER TABLE state_transitions
            ALTER COLUMN actor_id SET NOT NULL
    """)
    op.execute("""
        ALTER TABLE state_transitions
            ADD CONSTRAINT state_transitions_actor_id_fkey
            FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE RESTRICT
    """)
