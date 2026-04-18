"""Rate limit buckets table for Postgres-backed sliding-window rate limiter.

Replaces the Redis INCR+EXPIRE strategy with a single upsert on a
`rate_limit_buckets` table.  Each row represents one (identifier, minute)
bucket; the count column is incremented atomically in one SQL statement.

Revision ID: 0116_rate_limit_buckets
Revises: 0115_work_items_keyset_indexes
Create Date: 2026-04-18
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0116_rate_limit_buckets"
down_revision = "0115_work_items_keyset_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("identifier", sa.VARCHAR(255), nullable=False),
        sa.Column(
            "window_start_minute",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("identifier", "window_start_minute"),
    )
    # Supports periodic cleanup: DELETE WHERE window_start_minute < NOW() - INTERVAL '10 minutes'
    op.create_index(
        "ix_rate_limit_buckets_window",
        "rate_limit_buckets",
        ["window_start_minute"],
    )


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_window", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
