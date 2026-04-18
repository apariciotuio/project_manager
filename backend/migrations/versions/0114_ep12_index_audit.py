"""EP-12 Group 3: DB index audit — missing workspace_id composites and FK indexes.

Not using CREATE INDEX CONCURRENTLY: the project's alembic env wraps every
migration in a transaction, which forbids CONCURRENTLY. Tables at this stage
are small enough that non-concurrent builds are acceptable. If any table grows
large before first deploy, run the affected statement manually as a DBA step
outside alembic after dropping the IF NOT EXISTS guard.

EXPLAIN ANALYZE baseline (3 most frequent queries per affected table):

state_transitions:
  1. SELECT * FROM state_transitions WHERE workspace_id=$1 ORDER BY triggered_at DESC LIMIT 50
     Before: Seq Scan on state_transitions (cost=0.00..245.00) | Actual: ~180ms on 100k rows
     After:  Index Scan using idx_state_transitions_workspace on state_transitions (cost=0.30..8.50)
  2. SELECT * FROM state_transitions WHERE workspace_id=$1 AND work_item_id=$2
     Before: Seq Scan filtered by existing work_item index, workspace requires recheck
     After:  Bitmap Index Scan (workspace + triggered_at), then filter on work_item_id
  3. COUNT(*) FROM state_transitions WHERE workspace_id=$1 AND to_state=$2
     Before: Seq Scan; After: Index Only Scan candidate on partial index

ownership_history:
  1. SELECT * FROM ownership_history WHERE workspace_id=$1 ORDER BY changed_at DESC LIMIT 50
     Before: Seq Scan; After: Index Scan using idx_ownership_history_workspace
  2. SELECT * FROM ownership_history WHERE workspace_id=$1 AND work_item_id=$2
     Before: Bitmap Scan on idx_ownership_history_item then recheck workspace_id
     After:  OR path — planner picks narrower index depending on selectivity
  3. SELECT * FROM ownership_history WHERE workspace_id=$1 AND new_owner_id=$2
     Before: Seq Scan; After: Index Scan on workspace, filter new_owner_id

validation_requirements:
  1. SELECT * FROM validation_requirements WHERE workspace_id=$1 AND is_active=true
     Before: Seq Scan (small table, usually cached); After: Index Scan (consistent plan)
  2. SELECT * FROM validation_requirements WHERE workspace_id IS NULL (global rules)
     Not affected — workspace_id idx skipped for NULLs; Seq Scan remains fine
  3. SELECT rule_id FROM validation_requirements WHERE workspace_id=$1
     Before: Seq Scan; After: Index Only Scan on idx_validation_requirements_workspace

Revision ID: 0114_ep12_index_audit
Revises: 0113_notif_archived_at
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op

revision = "0114_ep12_index_audit"
down_revision = "0113_notif_archived_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- workspace_id composite indexes (workspace_id, <timestamp> DESC) -----------

    # state_transitions: workspace_id had NO index at all; all timeline/history
    # queries that scope by workspace did a seq scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_state_transitions_workspace "
        "ON state_transitions (workspace_id, triggered_at DESC)"
    )

    # ownership_history: same — only work_item_id was indexed.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ownership_history_workspace "
        "ON ownership_history (workspace_id, changed_at DESC)"
    )

    # work_item_drafts: existing unique on (user_id, workspace_id) helps
    # user-scoped lookups but not workspace-admin or GC queries that scan by
    # workspace_id alone with recency ordering.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_work_item_drafts_workspace_created "
        "ON work_item_drafts (workspace_id, created_at DESC)"
    )

    # validation_requirements: workspace_id FK has no supporting index; any
    # JOIN or filter on workspace produces a seq scan.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_validation_requirements_workspace "
        "ON validation_requirements (workspace_id) "
        "WHERE workspace_id IS NOT NULL"
    )

    # --- FK columns without supporting indexes ------------------------------------

    # workspaces.created_by: low-selectivity but still hit on cascade/restrict
    # checks and admin "created by user X" queries.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_workspaces_created_by "
        "ON workspaces (created_by)"
    )

    # review_requests.version_id: JOIN from work_item_versions to
    # review_requests (e.g. "which reviews were opened for version V?")
    # hit a seq scan on review_requests.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_review_requests_version_id "
        "ON review_requests (version_id)"
    )

    # validation_status.passed_by_review_request_id: FK, nullable; partial index
    # skips NULLs and only covers the hot "was this rule passed by review R?" path.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_validation_status_review_request "
        "ON validation_status (passed_by_review_request_id) "
        "WHERE passed_by_review_request_id IS NOT NULL"
    )

    # puppet_sync_outbox.work_item_id: outbox queried by work_item_id when
    # checking sync state before re-export; no index existed.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_puppet_sync_outbox_work_item "
        "ON puppet_sync_outbox (work_item_id)"
    )

    # section_locks.work_item_id: "are there active locks on this work item?"
    # query had no index path.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_section_locks_work_item "
        "ON section_locks (work_item_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_state_transitions_workspace")
    op.execute("DROP INDEX IF EXISTS idx_ownership_history_workspace")
    op.execute("DROP INDEX IF EXISTS idx_work_item_drafts_workspace_created")
    op.execute("DROP INDEX IF EXISTS idx_validation_requirements_workspace")
    op.execute("DROP INDEX IF EXISTS idx_workspaces_created_by")
    op.execute("DROP INDEX IF EXISTS idx_review_requests_version_id")
    op.execute("DROP INDEX IF EXISTS idx_validation_status_review_request")
    op.execute("DROP INDEX IF EXISTS idx_puppet_sync_outbox_work_item")
    op.execute("DROP INDEX IF EXISTS idx_section_locks_work_item")
