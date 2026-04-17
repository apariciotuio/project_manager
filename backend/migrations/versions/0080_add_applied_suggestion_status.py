"""EP-03 — add 'applied' to assistant_suggestions status check constraint.

Allows suggestions to transition from accepted → applied after
apply_accepted_batch writes their proposed_content to the section.

Revision ID: 0080_add_applied_suggestion_status
Revises: 0060_ep06_review_schema_fixes
Create Date: 2026-04-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0080_applied_suggestion"
down_revision = "0060_ep06_review_schema_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("assistant_suggestions_status_valid", "assistant_suggestions")
    op.create_check_constraint(
        "assistant_suggestions_status_valid",
        "assistant_suggestions",
        sa.text("status IN ('pending','accepted','rejected','expired','applied')"),
    )


def downgrade() -> None:
    op.drop_constraint("assistant_suggestions_status_valid", "assistant_suggestions")
    op.create_check_constraint(
        "assistant_suggestions_status_valid",
        "assistant_suggestions",
        sa.text("status IN ('pending','accepted','rejected','expired')"),
    )
