# EP-13 — Semantic Search + Puppet Integration

**Status:** backend **IN FLIGHT**; frontend **NOT STARTED**

Sub-trackers (authoritative):
- Backend: `tasks-backend.md`
- Frontend: `tasks-frontend.md`

## Phase summary

| Phase | Artifact | Status |
|-------|----------|--------|
| Proposal / Specs / Design | `proposal.md`, `specs/`, `design.md` | **COMPLETED** |
| Backend (outbox, Celery sync task to Puppet, ingest endpoints) | `tasks-backend.md` | **IN FLIGHT** — outbox + Celery task shipped; Puppet platform-ingestion endpoints pending |
| Frontend (search bar wiring, results page, result-to-detail link) | `tasks-frontend.md` | **NOT STARTED** |
| Code review + review-before-push | — | Pending |

## Dependencies

Depends on EP-09 (listings/dashboards scaffolding), EP-10 (admin/integration config), EP-12 (security/rate limits on external calls). See `tasks/tasks.md` dependency table.
