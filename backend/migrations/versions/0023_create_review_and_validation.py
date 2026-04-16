"""EP-06 Phase 1 — review_requests + review_responses + validation_requirements + validation_status.

Revision ID: 0023_review_and_validation
Revises: 0022_create_task_nodes
Create Date: 2026-04-16

Team-based review path is prepared in the schema (team_id NULLable with no FK
yet) but no FK to `teams` is added because the teams table lives in EP-08.
EP-08 migration will add the FK constraint once the teams table exists.
"""
from __future__ import annotations

from alembic import op

revision = "0023_review_and_validation"
down_revision = "0022_task_nodes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE validation_requirements (
            rule_id      VARCHAR(100) PRIMARY KEY,
            label        VARCHAR(255) NOT NULL,
            required     BOOLEAN NOT NULL DEFAULT FALSE,
            applies_to   TEXT NOT NULL DEFAULT ''
        )
    """)

    op.execute("""
        CREATE TABLE review_requests (
            id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id       UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
            version_id         UUID NOT NULL REFERENCES work_item_versions(id),
            reviewer_type      VARCHAR(10) NOT NULL,
            reviewer_id        UUID REFERENCES users(id),
            team_id            UUID,
            validation_rule_id VARCHAR(100)
                REFERENCES validation_requirements(rule_id),
            status             VARCHAR(15) NOT NULL DEFAULT 'pending',
            requested_by       UUID NOT NULL REFERENCES users(id),
            requested_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            cancelled_at       TIMESTAMPTZ,

            CONSTRAINT review_requests_reviewer_type_valid
                CHECK (reviewer_type IN ('user', 'team')),
            CONSTRAINT review_requests_status_valid
                CHECK (status IN ('pending', 'closed', 'cancelled')),
            CONSTRAINT chk_reviewer_target CHECK (
                (reviewer_type = 'user' AND reviewer_id IS NOT NULL AND team_id IS NULL)
                OR (reviewer_type = 'team' AND team_id IS NOT NULL AND reviewer_id IS NULL)
            )
        )
    """)
    op.execute(
        "CREATE INDEX idx_review_requests_work_item ON review_requests(work_item_id)"
    )
    op.execute(
        "CREATE INDEX idx_review_requests_status ON review_requests(work_item_id, status)"
    )
    op.execute("""
        CREATE INDEX idx_review_requests_reviewer_pending
        ON review_requests(reviewer_id, status)
        WHERE reviewer_id IS NOT NULL AND status = 'pending'
    """)
    op.execute("""
        CREATE INDEX idx_review_requests_team_pending
        ON review_requests(team_id, status)
        WHERE team_id IS NOT NULL AND status = 'pending'
    """)

    op.execute("""
        CREATE TABLE review_responses (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            review_request_id UUID NOT NULL REFERENCES review_requests(id)
                ON DELETE CASCADE,
            responder_id      UUID NOT NULL REFERENCES users(id),
            decision          VARCHAR(20) NOT NULL,
            content           TEXT,
            responded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

            CONSTRAINT review_responses_decision_valid
                CHECK (decision IN ('approved', 'rejected', 'changes_requested')),
            CONSTRAINT review_responses_content_required_when_not_approved
                CHECK (decision = 'approved' OR content IS NOT NULL)
        )
    """)
    op.execute(
        "CREATE INDEX idx_review_responses_request ON review_responses(review_request_id)"
    )

    op.execute("""
        CREATE TABLE validation_status (
            id                              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            work_item_id                    UUID NOT NULL REFERENCES work_items(id)
                ON DELETE CASCADE,
            rule_id                         VARCHAR(100) NOT NULL
                REFERENCES validation_requirements(rule_id),
            status                          VARCHAR(15) NOT NULL DEFAULT 'pending',
            passed_at                       TIMESTAMPTZ,
            passed_by_review_request_id     UUID REFERENCES review_requests(id),
            waived_at                       TIMESTAMPTZ,
            waived_by                       UUID REFERENCES users(id),
            waive_reason                    TEXT,

            CONSTRAINT validation_status_status_valid
                CHECK (status IN ('pending', 'passed', 'waived', 'obsolete')),
            CONSTRAINT uq_validation_status UNIQUE (work_item_id, rule_id)
        )
    """)
    op.execute(
        "CREATE INDEX idx_validation_status_work_item ON validation_status(work_item_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS validation_status")
    op.execute("DROP TABLE IF EXISTS review_responses")
    op.execute("DROP TABLE IF EXISTS review_requests")
    op.execute("DROP TABLE IF EXISTS validation_requirements")
