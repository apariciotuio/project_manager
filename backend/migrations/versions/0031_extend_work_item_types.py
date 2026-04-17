"""EP-14 follow-up: extend work_items.type CHECK to include story + milestone.

Migration 0030's comment claimed no DDL was required, but the DB-level
CHECK constraint from 0009 still rejects the new hierarchy types. Rebuild it
with the full enum surface.
"""
from __future__ import annotations

from alembic import op

revision = "0031_extend_work_item_types"
down_revision = "0030_ep14_15_16_17"
branch_labels = None
depends_on = None


_OLD_TYPES = ("idea", "bug", "enhancement", "task", "initiative", "spike", "business_change", "requirement")
_NEW_TYPES = _OLD_TYPES + ("story", "milestone")


def upgrade() -> None:
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS work_items_type_valid")
    values = ", ".join(f"'{t}'" for t in _NEW_TYPES)
    op.execute(
        f"ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid "
        f"CHECK (type IN ({values}))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS work_items_type_valid")
    values = ", ".join(f"'{t}'" for t in _OLD_TYPES)
    op.execute(
        f"ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid "
        f"CHECK (type IN ({values}))"
    )
