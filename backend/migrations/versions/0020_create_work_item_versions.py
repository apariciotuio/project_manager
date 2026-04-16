"""EP-04 Phase 1d — create work_item_versions table.

Revision ID: 0020_create_work_item_versions
Revises: 0019_create_work_item_validators
Create Date: 2026-04-16

Full-snapshot version log. Append-only. Never UPDATE rows.

Consumed by EP-06 (review pinning via review_requests.version_id), EP-07
(timeline/diff), and EP-11 (export snapshots).

**Single-writer invariant**: EP-07's VersioningService owns all writes. Other
services (EP-04 SectionService, EP-01 WorkItemService, EP-05 TaskService) call
VersioningService.create_version(...) rather than INSERTing directly.

EP-07 adds trigger/actor_type/commit_message columns via additive migration.
"""
from __future__ import annotations

from alembic import op

revision = "0020_work_item_versions"
down_revision = "0019_work_item_validators"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE work_item_versions (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            version_number  INTEGER NOT NULL,
            snapshot        JSONB NOT NULL,
            created_by      UUID NOT NULL REFERENCES users(id),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT uq_work_item_version UNIQUE (work_item_id, version_number)
        )
    """)

    op.execute("""
        CREATE INDEX idx_wiv_work_item_created
            ON work_item_versions(work_item_id, created_at DESC)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_wiv_work_item_created")
    op.execute("DROP TABLE IF EXISTS work_item_versions")
