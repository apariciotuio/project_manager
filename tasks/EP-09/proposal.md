# EP-09 — Listings, Dashboards, Search & Autonomous Workspace

## Business Need

The system must be fully operational without Jira. Users need to list, filter, search, and visualize work across multiple dimensions: by state, by owner, by team, as a pipeline. This is what makes it a workspace, not just a form.

## Objectives

- List work items with filters (state, owner, type, team, project)
- Provide global dashboard with aggregated metrics by state
- Provide dashboards by responsible person and by team
- Show pipeline/flow view of maturation stages
- Implement full-text search with context recovery
- Provide unified work view (detail integrated with all related data)

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-090 | List elements with filters and quick views | Must |
| US-091 | View global dashboard | Must |
| US-092 | View dashboards by responsible and by team | Must |
| US-093 | View workflow pipeline | Should |
| US-094 | Search and recover context | Must |
| US-095 | View unified work view | Must |

## Acceptance Criteria

- WHEN listing elements THEN filters for state, owner, type, team, and project are available
- WHEN viewing global dashboard THEN counts by state, blocked items, and aging metrics are shown
- WHEN viewing by-team dashboard THEN team workload and pending reviews are visible
- WHEN viewing pipeline THEN elements flow through maturation stages visually
- WHEN searching THEN full-text search covers titles, descriptions, specs, and comments
- WHEN the system has no Jira configured THEN all views function identically
- AND the detail view integrates spec, tasks, reviews, comments, and timeline

## Technical Notes

- Optimized list APIs with pagination, filtering, sorting
- Aggregation queries for dashboard metrics (consider materialized views or cached aggregations)
- Full-text search (DB-native or lightweight search index)
- Pipeline view: group-by state with counts and aging
- All views work without Jira — Jira status is additive info only

## Dependencies

- EP-01 (work items to list)
- EP-02 (elements to display)
- EP-06 (review status for dashboards)
- EP-08 (teams for team dashboards)

## Complexity Assessment

**Medium-High** — Individual views are standard, but the aggregation queries, search index, and pipeline visualization add up. Performance at scale is the main concern.

## Risks

- Dashboard queries slow down with data growth
- Search quality too low without proper indexing
- Pipeline view misleading if state machine has edge cases
