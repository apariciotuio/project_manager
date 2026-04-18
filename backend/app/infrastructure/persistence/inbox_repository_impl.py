"""EP-08 Group C — InboxRepositoryImpl.

UNION query with all four tiers.  De-duplication at SQL level via
ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY tier ASC) — only the
row with the lowest tier per item is returned.

Tier definitions (from spec, backend_review.md corrections applied):
  Tier 1 — review_requests where:
              (reviewer_type='user' AND reviewer_id = user_id)
              OR (reviewer_type='team' AND team_id IN user's active teams)
              AND status = 'pending'
              AND NOT already resolved by another member
  Tier 2 — work_items where owner_id = user_id AND state = 'changes_requested'
  Tier 3 — review_responses where responder_id = user_id AND decision = 'changes_requested'
              AND linked review_request still pending
  Tier 4 — work_items where owner_id = user_id AND state IN ('draft','in_clarification')
              AND completeness_score < 50

Indexes required (migration C2.1):
  - review_requests(reviewer_id, status) WHERE reviewer_id IS NOT NULL AND status='pending'
  - review_requests(team_id, status) WHERE reviewer_type='team' AND status='pending'
  - work_items(owner_id, state, workspace_id) WHERE deleted_at IS NULL
"""

from __future__ import annotations

from datetime import UTC
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.inbox_repository import IInboxRepository, InboxItem

# ---------------------------------------------------------------------------
# SQL fragments
# ---------------------------------------------------------------------------

_INBOX_UNION_SQL = text("""
WITH user_teams AS (
    SELECT tm.team_id
    FROM   team_memberships tm
    WHERE  tm.user_id     = :user_id
      AND  tm.removed_at  IS NULL
),
tier1_direct AS (
    SELECT
        rr.work_item_id                     AS item_id,
        wi.type                             AS item_type,
        wi.title                            AS item_title,
        wi.owner_id                         AS owner_id,
        wi.state                            AS current_state,
        1                                   AS priority_tier,
        'Pending reviews'                   AS tier_label,
        rr.requested_at                     AS event_age,
        '/items/' || rr.work_item_id        AS deeplink,
        NULL::jsonb                         AS quick_action,
        'direct'                            AS source,
        NULL::uuid                          AS team_id
    FROM   review_requests rr
    JOIN   work_items wi ON wi.id = rr.work_item_id
    WHERE  rr.reviewer_type = 'user'
      AND  rr.reviewer_id   = :user_id
      AND  rr.status        = 'pending'
      AND  wi.workspace_id  = :workspace_id
      AND  wi.deleted_at    IS NULL
),
tier1_team AS (
    SELECT
        rr.work_item_id                     AS item_id,
        wi.type                             AS item_type,
        wi.title                            AS item_title,
        wi.owner_id                         AS owner_id,
        wi.state                            AS current_state,
        1                                   AS priority_tier,
        'Pending reviews'                   AS tier_label,
        rr.requested_at                     AS event_age,
        '/items/' || rr.work_item_id        AS deeplink,
        NULL::jsonb                         AS quick_action,
        'team'                              AS source,
        rr.team_id                          AS team_id
    FROM   review_requests rr
    JOIN   work_items wi ON wi.id = rr.work_item_id
    JOIN   user_teams  ut ON ut.team_id = rr.team_id
    WHERE  rr.reviewer_type = 'team'
      AND  rr.status        = 'pending'
      AND  wi.workspace_id  = :workspace_id
      AND  wi.deleted_at    IS NULL
      -- exclude reviews already resolved by another team member
      AND  NOT EXISTS (
               SELECT 1
               FROM   review_responses rsp
               WHERE  rsp.review_request_id = rr.id
                 AND  rsp.decision IN ('approved', 'changes_requested', 'declined')
           )
),
tier2 AS (
    SELECT
        wi.id                               AS item_id,
        wi.type                             AS item_type,
        wi.title                            AS item_title,
        wi.owner_id                         AS owner_id,
        wi.state                            AS current_state,
        2                                   AS priority_tier,
        'Returned items'                    AS tier_label,
        wi.updated_at                       AS event_age,
        '/items/' || wi.id                  AS deeplink,
        NULL::jsonb                         AS quick_action,
        'direct'                            AS source,
        NULL::uuid                          AS team_id
    FROM   work_items wi
    WHERE  wi.owner_id     = :user_id
      AND  wi.state        = 'changes_requested'
      AND  wi.workspace_id = :workspace_id
      AND  wi.deleted_at   IS NULL
),
tier3 AS (
    SELECT
        rsp.review_request_id               AS item_id,
        'review'                            AS item_type,
        wi.title                            AS item_title,
        wi.owner_id                         AS owner_id,
        rr.status                           AS current_state,
        3                                   AS priority_tier,
        'Blocking items'                    AS tier_label,
        rsp.responded_at                    AS event_age,
        '/items/' || rr.work_item_id        AS deeplink,
        NULL::jsonb                         AS quick_action,
        'direct'                            AS source,
        NULL::uuid                          AS team_id
    FROM   review_responses rsp
    JOIN   review_requests rr ON rr.id = rsp.review_request_id
    JOIN   work_items wi ON wi.id = rr.work_item_id
    WHERE  rsp.responder_id  = :user_id
      AND  rsp.decision      = 'changes_requested'
      AND  rr.status         = 'pending'
      AND  wi.workspace_id   = :workspace_id
      AND  wi.deleted_at     IS NULL
),
tier4 AS (
    SELECT
        wi.id                               AS item_id,
        wi.type                             AS item_type,
        wi.title                            AS item_title,
        wi.owner_id                         AS owner_id,
        wi.state                            AS current_state,
        4                                   AS priority_tier,
        'Decisions needed'                  AS tier_label,
        wi.updated_at                       AS event_age,
        '/items/' || wi.id                  AS deeplink,
        NULL::jsonb                         AS quick_action,
        'direct'                            AS source,
        NULL::uuid                          AS team_id
    FROM   work_items wi
    WHERE  wi.owner_id          = :user_id
      AND  wi.state             IN ('draft', 'in_clarification')
      AND  wi.completeness_score < 50
      AND  wi.workspace_id      = :workspace_id
      AND  wi.deleted_at        IS NULL
),
all_tiers AS (
    SELECT * FROM tier1_direct
    UNION ALL
    SELECT * FROM tier1_team
    UNION ALL
    SELECT * FROM tier2
    UNION ALL
    SELECT * FROM tier3
    UNION ALL
    SELECT * FROM tier4
),
deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY priority_tier ASC) AS rn
    FROM   all_tiers
)
SELECT
    item_id,
    item_type,
    item_title,
    owner_id,
    current_state,
    priority_tier,
    tier_label,
    event_age,
    deeplink,
    quick_action,
    source,
    team_id
FROM deduped
WHERE rn = 1
{type_filter}
ORDER BY priority_tier ASC, event_age DESC
""")

_COUNT_SQL = text("""
WITH user_teams AS (
    SELECT tm.team_id
    FROM   team_memberships tm
    WHERE  tm.user_id     = :user_id
      AND  tm.removed_at  IS NULL
),
tier1_direct AS (
    SELECT rr.work_item_id AS item_id, 1 AS priority_tier
    FROM   review_requests rr
    JOIN   work_items wi ON wi.id = rr.work_item_id
    WHERE  rr.reviewer_type = 'user'
      AND  rr.reviewer_id   = :user_id
      AND  rr.status        = 'pending'
      AND  wi.workspace_id  = :workspace_id
      AND  wi.deleted_at    IS NULL
),
tier1_team AS (
    SELECT rr.work_item_id AS item_id, 1 AS priority_tier
    FROM   review_requests rr
    JOIN   work_items wi ON wi.id = rr.work_item_id
    JOIN   user_teams  ut ON ut.team_id = rr.team_id
    WHERE  rr.reviewer_type = 'team'
      AND  rr.status        = 'pending'
      AND  wi.workspace_id  = :workspace_id
      AND  wi.deleted_at    IS NULL
      AND  NOT EXISTS (
               SELECT 1 FROM review_responses rsp
               WHERE  rsp.review_request_id = rr.id
                 AND  rsp.decision IN ('approved', 'changes_requested', 'declined')
           )
),
tier2 AS (
    SELECT wi.id AS item_id, 2 AS priority_tier
    FROM   work_items wi
    WHERE  wi.owner_id     = :user_id
      AND  wi.state        = 'changes_requested'
      AND  wi.workspace_id = :workspace_id
      AND  wi.deleted_at   IS NULL
),
tier3 AS (
    SELECT rsp.review_request_id AS item_id, 3 AS priority_tier
    FROM   review_responses rsp
    JOIN   review_requests rr ON rr.id = rsp.review_request_id
    JOIN   work_items wi ON wi.id = rr.work_item_id
    WHERE  rsp.responder_id  = :user_id
      AND  rsp.decision      = 'changes_requested'
      AND  rr.status         = 'pending'
      AND  wi.workspace_id   = :workspace_id
      AND  wi.deleted_at     IS NULL
),
tier4 AS (
    SELECT wi.id AS item_id, 4 AS priority_tier
    FROM   work_items wi
    WHERE  wi.owner_id          = :user_id
      AND  wi.state             IN ('draft', 'in_clarification')
      AND  wi.completeness_score < 50
      AND  wi.workspace_id      = :workspace_id
      AND  wi.deleted_at        IS NULL
),
all_tiers AS (
    SELECT * FROM tier1_direct
    UNION ALL SELECT * FROM tier1_team
    UNION ALL SELECT * FROM tier2
    UNION ALL SELECT * FROM tier3
    UNION ALL SELECT * FROM tier4
),
deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (PARTITION BY item_id ORDER BY priority_tier ASC) AS rn
    FROM   all_tiers
)
SELECT priority_tier, COUNT(*) AS cnt
FROM   deduped
WHERE  rn = 1
GROUP  BY priority_tier
""")


class InboxRepositoryImpl(IInboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_inbox(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> list[InboxItem]:
        type_filter = ""
        if item_type is not None:
            type_filter = "AND item_type = :item_type"

        # Inject type filter into the SQL template by rebuilding the text
        sql_str = _INBOX_UNION_SQL.text.replace("{type_filter}", type_filter)
        stmt = text(sql_str)

        params: dict = {"user_id": user_id, "workspace_id": workspace_id}
        if item_type is not None:
            params["item_type"] = item_type

        rows = (await self._session.execute(stmt, params)).mappings().all()
        result = []
        for row in rows:
            event_age = row["event_age"]
            if event_age is not None and event_age.tzinfo is None:
                event_age = event_age.replace(tzinfo=UTC)
            result.append(
                InboxItem(
                    item_id=row["item_id"],
                    item_type=row["item_type"],
                    item_title=row["item_title"],
                    owner_id=row["owner_id"],
                    current_state=row["current_state"],
                    priority_tier=row["priority_tier"],
                    tier_label=row["tier_label"],
                    event_age=event_age,
                    deeplink=row["deeplink"],
                    quick_action=row["quick_action"],
                    source=row["source"],
                    team_id=row["team_id"],
                )
            )
        return result

    async def get_counts(
        self,
        user_id: UUID,
        workspace_id: UUID,
        *,
        item_type: str | None = None,
    ) -> dict[int, int]:
        # For counts with type filter, reuse get_inbox and count in Python
        # to avoid duplicating the SQL template logic
        if item_type is not None:
            items = await self.get_inbox(user_id, workspace_id, item_type=item_type)
            counts: dict[int, int] = {}
            for item in items:
                counts[item.priority_tier] = counts.get(item.priority_tier, 0) + 1
            return counts

        params = {"user_id": user_id, "workspace_id": workspace_id}
        rows = (await self._session.execute(_COUNT_SQL, params)).mappings().all()
        return {int(row["priority_tier"]): int(row["cnt"]) for row in rows}
