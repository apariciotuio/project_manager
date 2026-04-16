"""EP-05 Phase 1a — create task_nodes + task_node_section_links + task_dependencies.

Revision ID: 0022_create_task_nodes
Revises: 0021_add_section_id_to_assistant_suggestions
Create Date: 2026-04-16

Adjacency list + materialised path (see design.md §2). Path is maintained by
the application layer — no triggers.

task_node_section_links is the many-to-many bridge between task nodes and
spec sections (merge operations produce multiple links on a single task).

task_dependencies are explicit DAG edges; cross-work-item dependencies allowed.
"""
from __future__ import annotations

from alembic import op

revision = "0022_task_nodes"
down_revision = "0021_suggestions_section_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.execute("""
        CREATE TABLE task_nodes (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id      UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            parent_id         UUID REFERENCES task_nodes(id) ON DELETE CASCADE,
            title             VARCHAR(512) NOT NULL,
            description       TEXT NOT NULL DEFAULT '',
            display_order     SMALLINT NOT NULL,
            status            VARCHAR(32) NOT NULL DEFAULT 'draft',
            generation_source VARCHAR(16) NOT NULL DEFAULT 'llm',
            materialized_path TEXT NOT NULL DEFAULT '',
            created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by        UUID NOT NULL REFERENCES users(id),
            updated_by        UUID NOT NULL REFERENCES users(id),

            CONSTRAINT task_nodes_status_valid
                CHECK (status IN ('draft', 'in_progress', 'done')),
            CONSTRAINT task_nodes_generation_source_valid
                CHECK (generation_source IN ('llm', 'manual'))
        )
    """)
    op.execute("CREATE INDEX idx_task_nodes_work_item_id ON task_nodes(work_item_id)")
    op.execute("CREATE INDEX idx_task_nodes_parent_id ON task_nodes(parent_id)")
    op.execute(
        "CREATE INDEX idx_task_nodes_mat_path ON task_nodes "
        "USING gin(materialized_path gin_trgm_ops)"
    )

    op.execute("""
        CREATE TABLE task_node_section_links (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id    UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
            section_id UUID NOT NULL REFERENCES work_item_sections(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT uq_task_section_link UNIQUE (task_id, section_id)
        )
    """)
    op.execute("CREATE INDEX idx_tnsl_task_id ON task_node_section_links(task_id)")
    op.execute(
        "CREATE INDEX idx_tnsl_section_id ON task_node_section_links(section_id)"
    )

    op.execute("""
        CREATE TABLE task_dependencies (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_id  UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
            target_id  UUID NOT NULL REFERENCES task_nodes(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID NOT NULL REFERENCES users(id),

            CONSTRAINT uq_task_dependency UNIQUE (source_id, target_id),
            CONSTRAINT no_self_dependency CHECK (source_id != target_id)
        )
    """)
    op.execute("CREATE INDEX idx_task_dep_source ON task_dependencies(source_id)")
    op.execute("CREATE INDEX idx_task_dep_target ON task_dependencies(target_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS task_dependencies")
    op.execute("DROP TABLE IF EXISTS task_node_section_links")
    op.execute("DROP TABLE IF EXISTS task_nodes")
