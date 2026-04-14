# EP-11 Frontend Subtasks — Export & Sync with Jira

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS, React Query
**Depends on**: EP-09 (WorkItemDetail page where export UI lives), EP-10 frontend (Jira config/export history viewer from admin), EP-12 (API client, SkeletonLoader, ErrorBoundary)

> **Scope (2026-04-14, decisions_pending.md #5/#12/#26)**: No polling, no webhooks, no automated sync. Export UI is upsert-by-key (re-export UPDATEs the same Jira issue). New user-initiated "Import from Jira" action added below.

---

## Blocked by backend

| Component/Feature | Blocked by backend API |
|---|---|
| Export trigger button | `POST /api/v1/work-items/{id}/export` |
| Export history list | `GET /api/v1/work-items/{id}/exports` |
| Retry export | `POST /api/v1/exports/{id}/retry` |

The divergence indicator depends on the `diverged` field returned by `GET /api/v1/work-items/{id}` (EP-09 detail endpoint also returns this field).

---

## API Client Functions

### Acceptance Criteria

WHEN `triggerExport(workItemId)` receives HTTP 422
THEN it rejects with a typed error containing `error.code` (one of: `ELEMENT_NOT_READY`, `JIRA_CONFIG_NOT_FOUND`, `JIRA_CONFIG_DEGRADED`, `JIRA_PROJECT_MAPPING_NOT_FOUND`)
AND the calling component can pattern-match on `error.code` to render the correct message

WHEN `triggerExport(workItemId)` receives HTTP 409 `EXPORT_ALREADY_IN_PROGRESS`
THEN it rejects with a typed error containing the `export_id` from the response body

WHEN `retryExport(exportId)` receives HTTP 403
THEN it rejects with a typed `CapabilityError` (caller hides the button rather than showing an error)

## API Client Functions

- [ ] [RED] Write tests for `triggerExport(workItemId)` — calls POST, returns `{ export_id, status }`, handles 422/409 with typed errors
- [ ] [RED] Write tests for `getExportHistory(workItemId)` — returns `{ exports[], diverged }`
- [ ] [RED] Write tests for `retryExport(exportId)` — calls POST, returns `{ export_id, status }`, handles 403/422
- [ ] [GREEN] Implement all three API client functions in `lib/api/exports.ts`
- [ ] All functions attach `X-Correlation-ID` header via shared API client (EP-12)

---

## Group 1 — Export Button & Status (in WorkItemDetail, EP-09)

This UI lives inside the work item detail view, not a separate page.

### Acceptance Criteria — ExportButton

WHEN `state !== 'ready'`
THEN the export button is absent from the DOM (not just disabled)

WHEN the export button is clicked and the call is in flight
THEN the button shows a spinner, the label changes to "Exporting...", and the button is disabled to prevent double-submit

WHEN HTTP 202 is received
THEN a success toast shows "Export queued"
AND the button becomes disabled with label "Export in progress"
AND the export history query is invalidated (React Query)

WHEN HTTP 422 `JIRA_CONFIG_NOT_FOUND` is received
THEN inline error renders: "No Jira integration configured for this project"

WHEN HTTP 422 `JIRA_CONFIG_DEGRADED` is received
THEN inline error renders: "Jira integration is currently unavailable" with a link to the admin integrations page

WHEN HTTP 422 `JIRA_PROJECT_MAPPING_NOT_FOUND` is received
THEN inline error renders: "No Jira project mapping configured"

WHEN HTTP 409 `EXPORT_ALREADY_IN_PROGRESS` is received
THEN inline notice renders: "Export already in progress" — no second trigger is possible

### ExportButton (`components/detail/ExportButton.tsx`)
- [ ] [RED] Test: button renders when `state === 'ready'`; button absent or disabled when `state !== 'ready'`
- [ ] [RED] Test: clicking triggers `POST /work-items/{id}/export`; button enters loading state during call
- [ ] [RED] Test: on 202 response, shows "Export queued" success toast; button becomes disabled with "Export in progress" label
- [ ] [RED] Test: on 422 `ELEMENT_NOT_READY`, shows inline error (should not happen if guarded, but handle anyway)
- [ ] [RED] Test: on 422 `JIRA_CONFIG_NOT_FOUND`, shows inline error: "No Jira integration configured for this project"
- [ ] [RED] Test: on 422 `JIRA_CONFIG_DEGRADED`, shows inline error: "Jira integration is currently unavailable" with link to admin integrations page
- [ ] [RED] Test: on 422 `JIRA_PROJECT_MAPPING_NOT_FOUND`, shows inline error: "No Jira project mapping configured"
- [ ] [RED] Test: on 409 `EXPORT_ALREADY_IN_PROGRESS`, shows inline notice: "Export already in progress" (no second trigger)
- [ ] [GREEN] Implement `ExportButton` client component
- [ ] [GREEN] Use React Query `useMutation` for the export trigger; invalidate `exportHistory` query on success

### Placement in WorkItemDetail
- [ ] [GREEN] Wire `ExportButton` into `HeaderSection` or `StickyActionBar` (mobile) within `WorkItemDetail` (EP-09)
- [ ] [GREEN] Show Jira issue badge (`jira_key` chip linking to `jira_issue_url`) in header when latest export has status=success

---

## Group 2 — Divergence Indicator

### Acceptance Criteria

WHEN `diverged=true` from `GET /work-items/{id}`
THEN `DivergenceWarning` renders with banner text: "This work item has been modified since it was last exported to Jira"
AND a "Re-export" button is present in the banner

WHEN `diverged=false` or the work item has never been exported
THEN `DivergenceWarning` is absent from the DOM

WHEN the "Re-export" button is clicked
THEN it follows the same flow as `ExportButton` (same error handling, same mutation)
AND on success, the divergence banner disappears (query invalidated)

## Group 2 — Divergence Indicator

- [ ] [RED] Test: `DivergenceWarning` renders when `diverged=true` from `GET /work-items/{id}` response
- [ ] [RED] Test: banner text: "This work item has been modified since it was last exported to Jira"; shows "Re-export" button
- [ ] [RED] Test: `DivergenceWarning` absent when `diverged=false` or no export exists
- [ ] [GREEN] Implement `DivergenceWarning` banner component (`components/detail/DivergenceWarning.tsx`)
- [ ] [GREEN] "Re-export" button in banner reuses `ExportButton` logic
- [ ] [GREEN] Wire into `WorkItemDetail` next to the Jira badge in header

---

## Group 3 — Export History (`components/detail/ExportHistorySection.tsx`)

### Acceptance Criteria

WHEN `ExportHistorySection` mounts
THEN the accordion is collapsed; the export history API is NOT called until the user expands it

WHEN the accordion is expanded
THEN `useExportHistory(workItemId)` fires; a skeleton renders during fetch

WHEN the API returns export records
THEN each record shows: status badge, `jira_issue_key` as a link to `jira_issue_url` (new tab), `exported_at` date, `exported_by` display name

WHEN a record has `is_current_version=false`
THEN an "Outdated snapshot" warning badge renders on that record

WHEN a record has `jira_status = 'not_found'`
THEN the Jira status badge renders red with label "Not found in Jira"

WHEN a record has `status = 'failed'`
THEN `error_code` label and `attempt_count` are shown on the record

WHEN a record has `status = 'failed'` and the user has `retry_exports` capability
THEN a "Retry" button is visible on that record
AND clicking it calls `retryExport(exportId)`, shows a loading state, and refreshes the list on success

WHEN the user lacks `retry_exports` capability
THEN no "Retry" button appears on any record (absent, not disabled)

WHEN the API returns an empty array
THEN `EmptyState` renders with message "No exports yet"

## Group 3 — Export History (`components/detail/ExportHistorySection.tsx`)

- [ ] [RED] Test: section renders within WorkItemDetail (collapsed by default, expand on click)
- [ ] [RED] Test: renders list of export records with status badge, jira_issue_key link, exported_at date, exported_by name
- [ ] [RED] Test: `is_current_version=false` renders "Outdated snapshot" warning badge per record
- [ ] [RED] Test: `jira_status` badge renders correct label (open/in_progress/done/unknown/not_found)
- [ ] [RED] Test: failed export shows `error_code` label and attempt count
- [ ] [RED] Test: "Retry" button visible on failed records only; hidden if user lacks `retry_exports` capability
- [ ] [RED] Test: "Retry" button triggers `POST /exports/{id}/retry`, shows loading state, updates status on success
- [ ] [RED] Test: skeleton shown while fetching export history
- [ ] [RED] Test: empty state shown when no exports exist
- [ ] [GREEN] Implement `ExportHistorySection` as collapsible accordion within `WorkItemDetail`
- [ ] [GREEN] Status badges: pending (grey), success (green), failed (red), retrying (amber)
- [ ] [GREEN] Jira status badges: open (blue), in_progress (amber), done (green), not_found (red), unknown (grey)
- [ ] [GREEN] Capability guard: read `retry_exports` from current member context (EP-10 member context hook); hide retry if not present

---

## Group 4 — Jira Badge in Header

- [ ] [RED] Test: `JiraBadge` renders chip with `PROJ-123` label linking to `jira_issue_url` when `jira_issue_key` is set
- [ ] [RED] Test: badge absent when no successful export
- [ ] [RED] Test: badge shows `jira_status` icon (in_progress, done, not_found)
- [ ] [GREEN] Implement `JiraBadge` component (`components/detail/JiraBadge.tsx`)
- [ ] [GREEN] Wire into `HeaderSection` (EP-09)

---

## Group 5 — Hooks

- [ ] [GREEN] Implement `useExportHistory(workItemId)` — React Query fetch of `GET /work-items/{id}/exports`, returns `{ exports, diverged, isLoading, isError }`
- [ ] [GREEN] Implement `useExportTrigger(workItemId)` — React Query mutation, returns `{ trigger, isLoading, error }`
- [ ] [GREEN] Implement `useExportRetry(exportId)` — React Query mutation, invalidates `exportHistory` on success

---

## Group N — Import from Jira (decision #12)

### Acceptance Criteria

WHEN the user picks "Import from Jira" in the project work-item list
THEN a modal opens asking for a Jira issue key (e.g. `PROJ-123`)

WHEN the user confirms a valid Jira key
THEN `POST /api/v1/work-items/import-from-jira` is called with `{ jira_issue_key, project_id }`
AND on 201 the user is navigated to the new draft work-item detail page
AND on 422 `JIRA_ISSUE_NOT_FOUND` an inline error is shown ("Issue not found in Jira — check the key")
AND on 409 `ALREADY_IMPORTED` the user is offered a link to the existing work item

### Tasks

- [ ] [RED] Test: `importFromJira({ jira_issue_key, project_id })` API client — 201 returns work_item; 422 returns typed error; 409 returns typed error with `work_item_id`
- [ ] [GREEN] Implement `importFromJira` in `lib/api/imports.ts`
- [ ] [RED] Test: `ImportFromJiraModal` — input validation (`^[A-Z][A-Z0-9]+-\d+$`), submit calls API, success navigates, 422 shows inline error, 409 shows "Already imported — [open existing]"
- [ ] [GREEN] Implement `ImportFromJiraModal` in `components/imports/ImportFromJiraModal.tsx`
- [ ] [GREEN] Add "Import from Jira" action to project work-item list menu (visible only if user has `create_work_item` capability AND workspace has an active Jira config)

---

## Notes

- No separate page for export — all UI lives inside the work item detail view (EP-09).
- Admin-side Jira export history viewer is covered in EP-10 frontend (`JiraExportHistoryTable`). There is no `sync_logs` table (decision #26).
- Export status polling is NOT needed: the export history is fetched on section open. For real-time status updates if required in future, use EP-08 SSE infrastructure.
