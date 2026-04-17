"""EP-14 follow-up: extend work_items.type CHECK to include story + milestone.

Migration 0030's comment claimed no DDL was required, but the DB-level
CHECK constraint from 0009 still rejects the new hierarchy types. Rebuild it
with the full enum surface.

Concurrency notes:
  - Uses the two-step `ADD CONSTRAINT ... NOT VALID` + `VALIDATE CONSTRAINT`
    pattern so the ACCESS EXCLUSIVE lock is held only briefly. VALIDATE
    takes SHARE UPDATE EXCLUSIVE, which allows concurrent reads and writes.
  - Downgrade fails loudly if any row already uses `story` / `milestone`.
    Rolling back those types without a data plan would silently corrupt
    data or break the constraint, so we refuse instead.
"""
from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0031_extend_work_item_types"
down_revision = "0030_ep14_15_16_17"
branch_labels = None
depends_on = None


_OLD_TYPES = ("idea", "bug", "enhancement", "task", "initiative", "spike", "business_change", "requirement")
_NEW_TYPES = _OLD_TYPES + ("story", "milestone")


def _check_sql(types: tuple[str, ...]) -> str:
    values = ", ".join(f"'{t}'" for t in types)
    return f"type IN ({values})"


def upgrade() -> None:
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS work_items_type_valid")
    # Two-step: add NOT VALID (brief ACCESS EXCLUSIVE, no full-table scan),
    # then VALIDATE (SHARE UPDATE EXCLUSIVE, concurrent reads/writes allowed).
    op.execute(
        f"ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid "
        f"CHECK ({_check_sql(_NEW_TYPES)}) NOT VALID"
    )
    op.execute("ALTER TABLE work_items VALIDATE CONSTRAINT work_items_type_valid")


def downgrade() -> None:
    conn = op.get_bind()
    offending = conn.execute(
        text(
            "SELECT count(*) FROM work_items "
            "WHERE type IN ('story', 'milestone') AND deleted_at IS NULL"
        )
    ).scalar_one()
    if offending:
        raise RuntimeError(
            f"refusing to downgrade: {offending} work_items row(s) use "
            "type='story' or type='milestone'. Migrate them to a legacy type "
            "first (e.g. UPDATE work_items SET type='task' WHERE type IN (...)) "
            "or drop them."
        )
    op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS work_items_type_valid")
    op.execute(
        f"ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid "
        f"CHECK ({_check_sql(_OLD_TYPES)}) NOT VALID"
    )
    op.execute("ALTER TABLE work_items VALIDATE CONSTRAINT work_items_type_valid")
