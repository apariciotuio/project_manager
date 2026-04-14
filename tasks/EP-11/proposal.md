# EP-11 — Export & Sync with Jira

## Business Need

The bridge to execution. Only Ready elements can be exported, only via explicit user action, and only as an immutable snapshot. The system maintains the internal-external link and syncs basic status back from Jira. No silent or automatic exports.

## Objectives

- Export to Jira via explicit manual action only
- Block export for non-Ready elements
- Build and send final snapshot (immutable)
- Store Jira reference and display internal/external link
- Sync basic status from Jira (at minimum: status)
- Maintain controlled behavior post-export (snapshot is immutable, element can keep evolving)

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-110 | Send to Jira via explicit action | Must |
| US-111 | Build and send final snapshot | Must |
| US-112 | Store Jira reference and show internal/external link | Must |
| US-113 | Sync basic status from Jira | Should |
| US-114 | Maintain controlled post-export behavior | Must |

## Acceptance Criteria

- WHEN a user triggers export THEN the element must be in Ready state
- WHEN export is attempted on non-Ready element THEN the system blocks with clear message
- WHEN exported THEN the snapshot is immutable and identifiable
- WHEN the user views an exported element THEN the Jira ticket link is visible
- WHEN Jira status changes THEN the system reflects basic status (at minimum: open/in-progress/done)
- WHEN the element changes after export THEN the exported snapshot is preserved AND divergence is detectable
- AND export failures are logged with retry capability
- AND no automatic content modification in Jira post-export

## Technical Notes

- Decoupled integration via async jobs
- Idempotent export (retry-safe)
- Snapshot stored as immutable record linked to element version
- Jira API client (wrapped, not direct dependency in domain)
- Sync via polling or webhook (polling is acceptable) ⚠️ originally MVP-scoped — see decisions_pending.md
- Export logs with status, timestamps, error details

## Dependencies

- EP-01 (states — Ready gate)
- EP-04 (specification to export)
- EP-06 (validations must pass before Ready)
- EP-10 (Jira configuration)

## Complexity Assessment

**Medium-High** — Jira API integration, snapshot immutability, sync mechanism, and failure handling. The Jira API itself is well-documented but has quirks (field mappings, custom fields, project schemas).

## Risks

- Jira API rate limits or downtime during export
- Field mapping mismatches between internal model and Jira schema
- Sync drift (Jira status changes not reflected)
- Post-export element changes confuse users about what was actually exported
