"""EP-04 Phase 1e — wire EP-03 suggestions to EP-04 sections.

Revision ID: 0021_add_section_id_to_assistant_suggestions
Revises: 0020_create_work_item_versions
Create Date: 2026-04-16

EP-03 persisted `section_id` as a bare UUID column with no FK because the
`work_item_sections` table did not exist yet. Now that EP-04 has created it,
add the FK so integrity is enforced.

`ON DELETE SET NULL` — if a section is deleted the suggestion remains as
historical record. Existing rows with section_id pointing to nothing become
NULL via the constraint (the table is empty in dev/test anyway).
"""
from __future__ import annotations

from alembic import op

revision = "0021_suggestions_section_fk"
down_revision = "0020_work_item_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows may have orphan section_id pointing to a non-existent section.
    # Null them out before applying the FK.
    op.execute("""
        UPDATE assistant_suggestions AS s
        SET section_id = NULL
        WHERE s.section_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM work_item_sections ws WHERE ws.id = s.section_id
          )
    """)

    op.execute("""
        ALTER TABLE assistant_suggestions
        ADD CONSTRAINT fk_assistant_suggestions_section
            FOREIGN KEY (section_id)
            REFERENCES work_item_sections(id)
            ON DELETE SET NULL
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE assistant_suggestions
        DROP CONSTRAINT IF EXISTS fk_assistant_suggestions_section
    """)
