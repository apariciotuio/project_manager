"""Add partial index on team_memberships(team_id, joined_at) WHERE removed_at IS NULL.

Backs the `_resolve_members` query introduced with EP-08 team picker —
filters by team_id + removed_at IS NULL and orders by joined_at. Existing
unique constraint on (team_id, user_id) covers the team_id predicate but
not the ordering.

Not using CREATE INDEX CONCURRENTLY: the project's alembic env wraps every
migration in a transaction, which forbids CONCURRENTLY. `team_memberships`
is small enough that a non-concurrent build is acceptable; if that ever
stops being true, run this one ALTER as a manual DDL step outside alembic.
"""
from __future__ import annotations

from alembic import op

revision = "0032_team_memberships_idx"
down_revision = "0031_extend_work_item_types"
branch_labels = None
depends_on = None

INDEX_NAME = "idx_team_memberships_team_active"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        f"ON team_memberships (team_id, joined_at) "
        f"WHERE removed_at IS NULL"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
