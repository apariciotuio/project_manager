"""EP-12 work_items keyset pagination indexes — created_at composite.

The GET /api/v1/work-items endpoint uses keyset pagination with SortOption
values: updated_desc, updated_asc, created_desc, title_asc, completeness_desc.

idx_work_items_active (workspace_id, updated_at DESC) WHERE deleted_at IS NULL
already exists in the ORM model (added at model-definition time, not via a
migration file — present from the initial schema).

Missing: (workspace_id, created_at DESC) WHERE deleted_at IS NULL, which backs
the SortOption.created_desc keyset cursor path in WorkItemListQueryBuilder.
Without this index, a created_desc sort on any reasonably-sized workspace does
a full seq scan on work_items filtered by workspace_id.

Unsupported sorts without selective composite indexes (flagged, not added):
  - title_asc: text sort; a covering index on (workspace_id, title) would help
    but the cardinality/selectivity tradeoff is workspace-dependent. DBA to
    evaluate once table size warrants it.
  - completeness_desc: numeric sort on a frequently-updated column; index
    maintenance cost likely outweighs read gain at current scale. Revisit when
    completeness-sorted queries appear in slow-query logs.

Not using CREATE INDEX CONCURRENTLY: alembic env wraps every migration in a
transaction, which forbids CONCURRENTLY. If work_items has grown large before
first deploy, run the statement manually as a DBA step outside alembic after
removing the IF NOT EXISTS guard, then let this migration no-op on next run.

Revision ID: 0115_work_items_keyset_indexes
Revises: 0114_ep12_index_audit
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op

revision = "0115_work_items_keyset_indexes"
down_revision = "0114_ep12_index_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SortOption.created_desc keyset path: cursor anchors on (created_at, id)
    # scoped to workspace. Without this index the planner falls back to a seq
    # scan filtered by workspace_id then sorted — O(n) on workspace row count.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_items_workspace_created "
        "ON work_items (workspace_id, created_at DESC) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_work_items_workspace_created")
