# EP-10 Frontend Subtasks — Configuration, Projects, Rules & Administration

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS, React Query
**Depends on**: EP-12 layout primitives (AppShell, DataTable, EmptyState, SkeletonLoader, ErrorBoundary), EP-12 API client, EP-12 responsive patterns

---

## Blocked by backend

| Component/Feature | Blocked by backend API |
|---|---|
| Member list | `GET /api/v1/admin/members` |
| Invite flow | `POST /api/v1/admin/members` |
| Capabilities editor | `PATCH /api/v1/admin/members/{id}` |
| Validation rules | `GET/POST/PATCH/DELETE /api/v1/admin/rules/validation` |
| Routing rules | `GET/POST/PATCH/DELETE /api/v1/admin/rules/routing` |
| Projects list/form | `GET/POST/PATCH /api/v1/admin/projects` |
| Context sources | `GET/POST/PUT/DELETE /api/v1/admin/projects/{id}/context-sources` |
| Context presets | `GET/POST/PATCH/DELETE /api/v1/admin/context-presets` |
| Jira config | `GET/POST/PATCH /api/v1/admin/integrations/jira` |
| Jira test connection | `POST /api/v1/admin/integrations/jira/{id}/test` |
| Audit log | `GET /api/v1/admin/audit-log` |
| Admin health dashboard | `GET /api/v1/admin/dashboard` |
| Support tools | `GET/POST /api/v1/admin/support/*` |

---

## API Client Functions

- [ ] [GREEN] Implement `lib/api/admin/members.ts` — `listMembers`, `inviteMember`, `updateMember`, `resendInvitation`
- [ ] [GREEN] Implement `lib/api/admin/rules.ts` — `listValidationRules`, `createValidationRule`, `updateValidationRule`, `deleteValidationRule`, `listRoutingRules`, `createRoutingRule`, `updateRoutingRule`, `deleteRoutingRule`
- [ ] [GREEN] Implement `lib/api/admin/projects.ts` — `listProjects`, `createProject`, `updateProject`, `getProject`, `replaceContextSources`, `updateTemplateBindings`
- [ ] [GREEN] Implement `lib/api/admin/presets.ts` — `listContextPresets`, `createContextPreset`, `updateContextPreset`, `deleteContextPreset`
- [ ] [GREEN] Implement `lib/api/admin/jira.ts` — `listJiraConfigs`, `createJiraConfig`, `updateJiraConfig`, `testJiraConnection`, `listMappings`, `createMapping`, `listSyncLogs`, `retrySyncLog`
- [ ] [GREEN] Implement `lib/api/admin/audit.ts` — `getAuditLog(filters, cursor)`
- [ ] [GREEN] Implement `lib/api/admin/dashboard.ts` — `getAdminDashboard(projectId?)`
- [ ] [GREEN] Implement `lib/api/admin/support.ts` — `getOrphanedItems`, `reassignOwner`, `getPendingInvitations`, `getFailedExports`, `retryAllExports`, `getConfigBlockedItems`
- [ ] All functions use shared API client with correlation ID header (EP-12)

---

## Group 1 — Admin Layout & Shell

### Acceptance Criteria

WHEN a user with zero admin capabilities navigates to any `/admin/*` route
THEN they are redirected to `/` immediately (no flash of admin content)

WHEN a user has at least one admin capability and navigates to `/admin/*`
THEN the admin shell renders with the side navigation

WHEN the viewport is <768px
THEN the admin side navigation is hidden; a hamburger icon opens a drawer overlay

WHEN a user navigates between admin sections
THEN the active nav item is highlighted and `aria-current="page"` is set

## Group 1 — Admin Layout & Shell

- [ ] [RED] Test: admin routes are only reachable when `member.capabilities` contains at least one admin capability; redirect to `/` otherwise
- [ ] [GREEN] Implement `app/admin/layout.tsx` — admin section layout with capability guard
- [ ] [GREEN] Implement admin side navigation: Members, Rules, Projects, Integrations (Jira + Puppet), Tags, Audit Log, Dashboard, Support Tools
- [ ] [GREEN] Superadmin-only sections (visible only when `user.is_superadmin = true` from `/auth/me`): User Management (create user form), Cross-Workspace Audit — hide menu items completely, do not disable them
- [ ] [GREEN] Mobile: admin nav collapses to hamburger/drawer; side navigation on md+
- [ ] [GREEN] Active nav item highlighted per current route

---

## Group 2 — Members & Capabilities

### Member List (`app/admin/members/page.tsx`)
- [ ] [RED] Test: renders member list with state badges, capability chips, filter by state and teamless
- [ ] [RED] Test: empty state when no members
- [ ] [RED] Test: skeleton shown during fetch
- [ ] [GREEN] Implement member list page using `DataTable` component (EP-12)
- [ ] [GREEN] Columns: name/email, state badge, capabilities (truncated chips), teams, invited_at/joined_at, actions
- [ ] [GREEN] Filter controls: by state (active/invited/suspended/deleted), teamless toggle
- [ ] [GREEN] Cursor-based pagination via "Load more" or paginated DataTable

### Invite Member Form
- [ ] [RED] Test: email validation, context_labels multi-input, team_ids multi-select, submit calls invite API, success shows confirmation, 409 shows duplicate email error
- [ ] [GREEN] Implement `InviteMemberModal` (modal form, or slide-over panel on mobile as BottomSheet)
- [ ] [GREEN] Trigger from "Invite member" button in member list

### Acceptance Criteria — MemberCapabilityEditor

WHEN `MemberCapabilityEditor` renders
THEN 10 capability checkboxes are present, one per capability in the enum

WHEN the acting member does not hold capability X
THEN the checkbox for capability X is `disabled` and shows a tooltip explaining the constraint

WHEN `PATCH /api/v1/admin/members/{id}` returns HTTP 403
THEN an inline error renders below the form: "You cannot grant capabilities you don't hold"

WHEN the invite flow succeeds
THEN a confirmation message shows the invitee's email
AND the member list refreshes without full page reload

WHEN `POST /api/v1/admin/members` returns HTTP 409 `member_already_active`
THEN the modal form shows: "A member with this email already exists"

WHEN suspend/delete confirmation dialog is confirmed
THEN the API call is made and the member row updates state badge in place

### Edit Member Capabilities (`components/admin/MemberCapabilityEditor.tsx`)
- [ ] [RED] Test: checkboxes render for each capability, disabled if current user doesn't possess the capability (cannot grant unpossessed), submit calls PATCH, 403 shows inline error
- [ ] [GREEN] Implement `MemberCapabilityEditor` — checkbox grid for all 10 capabilities
- [ ] [GREEN] Disable capabilities the acting member doesn't hold (granting constraint)
- [ ] [GREEN] Context labels editor: tag-input component (add/remove text labels)

### Suspend / Delete / Reactivate Actions
- [ ] [RED] Test: suspend prompts confirmation dialog, reactivate prompts confirmation, delete prompts confirmation with orphan-owner warning
- [ ] [GREEN] Implement action menu on member row (suspend, reactivate, delete)
- [ ] [GREEN] Confirmation dialogs with consequence text

---

## Group 3 — Validation Rules

### Acceptance Criteria — Validation Rules UI

WHEN the rules list renders
THEN each validation rule row shows: work_item_type, validation_type, enforcement badge, scope (Workspace / Project), `effective` badge, and `superseded_by` indicator (rule ID if superseded)

WHEN `enforcement = blocked_override` is selected in the create/edit form
THEN a warning banner renders: "This will supersede any project-level rule of the same type"

WHEN the API returns HTTP 409 `rule_already_exists` on submit
THEN the form shows inline error: "A rule for this combination already exists" with the existing rule ID

WHEN a rule has usage history and the delete button is clicked
THEN the delete button is disabled with a tooltip: "Cannot delete — use Deactivate instead"

WHEN the API returns HTTP 409 `global_blocker_in_effect` on project-level rule creation
THEN the form shows inline error explaining that a workspace-level blocked_override rule is in effect

### Rule List (`app/admin/rules/page.tsx`)
- [ ] [RED] Test: renders validation and routing rule tables, shows `effective`/`superseded_by` annotation, workspace vs project scope labelled
- [ ] [GREEN] Implement rules page with two tabs: Validation Rules, Routing Rules
- [ ] [GREEN] Validation rule row: work_item_type, validation_type, enforcement badge, scope (workspace/project), effective badge, superseded_by indicator
- [ ] [GREEN] Filter: by work_item_type, by project, by active/inactive

### Create/Edit Validation Rule Form
- [ ] [RED] Test: form validation (all required fields), enforcement select (required/recommended/blocked_override), scope toggle (workspace vs project with project picker), submit creates/updates, duplicate 409 shows inline error
- [ ] [GREEN] Implement `ValidationRuleForm` modal/drawer
- [ ] [GREEN] `blocked_override` enforcement shows warning: "This will supersede any project-level rule of the same type"

### Routing Rule Form
- [ ] [RED] Test: optional fields, team picker, context label picker, submit
- [ ] [GREEN] Implement `RoutingRuleForm` modal/drawer

### Delete Rule
- [ ] [RED] Test: delete disabled when rule has history (409), enabled when no history; confirmation dialog
- [ ] [GREEN] Disable delete button with tooltip when rule has usage history

---

## Group 4 — Projects & Context

### Project List (`app/admin/projects/page.tsx`)
- [ ] [RED] Test: renders project list, state badge, team chips, preset indicator
- [ ] [GREEN] Implement project list page

### Create/Edit Project Form
- [ ] [RED] Test: name validation, team multi-select, context preset dropdown, template bindings editor, submit, duplicate name 409
- [ ] [GREEN] Implement `ProjectForm` (modal or full page for edit)
- [ ] [GREEN] Archive project: confirmation dialog with open-elements count warning

### Context Sources Editor (`components/admin/ContextSourcesEditor.tsx`)
- [ ] [RED] Test: add source (type/label/url/description), remove source, bulk replace via PUT, inline validation
- [ ] [GREEN] Implement context sources editor as inline list within project edit page
- [ ] [GREEN] Source types: enum select, label and URL required

### Context Presets (`app/admin/context-presets/page.tsx`)
- [ ] [RED] Test: list presets, create preset, edit sources, delete (disabled if in use — 409 shows which projects)
- [ ] [GREEN] Implement context presets list and CRUD forms
- [ ] [GREEN] Delete: show "in use by N projects" warning when 409 returned

### Template Bindings
- [ ] [GREEN] Implement `TemplateBundlingEditor` — key/value editor for template bindings JSONB field (within project edit)

---

## Group 5 — Jira Integration

### Acceptance Criteria — Jira Integration UI

WHEN a Jira config is in `error` state
THEN the config card shows a red badge with the consecutive failure streak count (e.g., "Error — 3 failures")

WHEN `base_url` is entered as HTTP (not HTTPS) in the create form
THEN client-side validation shows an inline error before submission

WHEN the `JiraConfigForm` edit mode renders
THEN credential fields (api_token, email) are empty — they are never pre-populated

WHEN "Test Connection" button is clicked
THEN the button shows a spinner and the label changes to "Testing..."
AND on result: `ok` shows a green checkmark + "Connection successful"; `auth_failure` shows red icon + error message; `unreachable` shows red icon + timeout message

WHEN `POST /api/v1/admin/integrations/jira/{id}/test` returns `{status: "auth_failure"}`
THEN the inline result shows "Authentication failed — check your API token"

WHEN the retry button in `JiraSyncLogTable` is clicked by a user lacking `retry_exports` capability
THEN the button is absent (not just disabled)

### Jira Config List (`app/admin/integrations/jira/page.tsx`)
- [ ] [RED] Test: renders config cards with state badge (active/disabled/error), health status, last check time
- [ ] [GREEN] Implement Jira integration list page
- [ ] [GREEN] State badges: active (green), disabled (grey), error (red with streak count)

### Create Jira Config Form
- [ ] [RED] Test: base URL validation (must be HTTPS), auth type select (API token, OAuth), credentials fields (never pre-filled on edit), submit creates config, server-side 422 shown inline
- [ ] [GREEN] Implement `JiraConfigForm` — credentials fields never show existing values (write-only UI)
- [ ] [GREEN] Credential fields: `email` + `api_token` for API token auth

### Test Connection
- [ ] [RED] Test: "Test Connection" button sends POST, shows spinner during call, renders ok/auth_failure/unreachable result inline
- [ ] [GREEN] Implement inline connection test result with status icon and message

### Project Mappings (`components/admin/JiraProjectMappings.tsx`)
- [ ] [RED] Test: list mappings, add mapping (jira project key, workspace project picker, type mappings table), submit
- [ ] [GREEN] Implement `JiraProjectMappings` as a section within config detail page
- [ ] [GREEN] Work item type mappings: table with platform type → Jira issue type ID mapping

### Sync Log Viewer
- [ ] [RED] Test: log list with status filter, pagination, retry button on failed log (requires RETRY_EXPORTS capability)
- [ ] [GREEN] Implement `JiraSyncLogTable` within config detail page
- [ ] [GREEN] Retry button: disabled if user lacks `retry_exports` capability (check from current member context)

---

## Group 5b — Puppet Integration (`app/admin/integrations/puppet/page.tsx`)

Admin nav entry: **Integrations** → sub-sections **Jira** and **Puppet**.

### Acceptance Criteria

WHEN a Puppet config is in `error` state
THEN the config card shows a red badge

WHEN `api_endpoint` is entered as HTTP (not HTTPS) in the create form
THEN client-side validation shows inline error before submission

WHEN the Puppet config form edit mode renders
THEN the API key field is empty — never pre-populated (write-only field)

WHEN "Test Connection" is clicked
THEN the button shows a spinner and on result: `ok` shows green checkmark; `auth_failure`/`unreachable` shows red icon + message

- [ ] [GREEN] Implement `lib/api/admin/puppet.ts` — `listPuppetConfigs`, `createPuppetConfig`, `updatePuppetConfig`, `testPuppetConnection`, `listSources`, `addSource`, `deleteSource`
- [ ] [RED] Test: renders config list with state badge, test-connection flow, form validation (HTTPS required)
- [ ] [GREEN] Implement Puppet integration list page
- [ ] [GREEN] Implement `PuppetConfigForm` — API key field is write-only (never pre-filled on edit)
- [ ] [GREEN] Documentation sources editor: add/remove URL entries inline
- [ ] [GREEN] Test Connection button: same spinner/result pattern as Jira

---

## Group 5c — Superadmin Sections

Visibility: render only when `user.is_superadmin = true` (from `/auth/me` response). Do not render disabled — omit entirely.

### User Management (`app/admin/users/new/page.tsx`)

- [ ] [RED] Test: form hidden when `is_superadmin = false`, visible when `true`
- [ ] [RED] Test: form validation (email, display_name required), workspace picker, initial capabilities multi-select, submit creates user, 409 shows duplicate email error
- [ ] [GREEN] Implement create-user form page (superadmin only)
- [ ] [GREEN] Route guarded by `is_superadmin` check — redirect to `/admin` if not superadmin

### Cross-Workspace Audit (`app/admin/audit/cross-workspace/page.tsx`)

- [ ] [RED] Test: page hidden when `is_superadmin = false`, renders full audit table when `true`
- [ ] [GREEN] Implement cross-workspace audit viewer — same filters as workspace audit log but no workspace scope constraint
- [ ] [GREEN] Each row shows `workspace_id` / workspace name column (not present in workspace-scoped audit log)
- [ ] [GREEN] Route guarded by `is_superadmin` check

---

## Group 5d — Tags Admin Entry Point

Tag management is implemented in EP-15. This epic adds the left-nav entry point.

- [ ] [GREEN] Admin left-nav entry: **Tags** → `/admin/tags` (route implemented in EP-15)
- [ ] [GREEN] Entry visible to members with `manage_tags` or `merge_tags` capability (or superadmin)

---

## Group 6 — Audit Log (`app/admin/audit-log/page.tsx`)

- [ ] [RED] Test: renders log table with actor, action, entity, date; filters (actor, action, entity_type, date range); pagination; empty state
- [ ] [GREEN] Implement audit log page using `DataTable`
- [ ] [GREEN] Filter bar: actor search, action type filter, entity type filter, date range picker
- [ ] [GREEN] Row detail: expand row to show before/after JSONB diff (collapsible)
- [ ] [GREEN] Cursor-based pagination, max 200 per page
- [ ] [RED] Test: 403 shown when user lacks `view_audit_log` capability (guard at page level)

---

## Group 7 — Admin Health Dashboard (`app/admin/dashboard/page.tsx`)

- [ ] [RED] Test: renders four health sections (workspace, org, process, integration), project scope selector
- [ ] [GREEN] Implement admin dashboard page

### WorkspaceHealthSection
- [ ] [RED] Test: state breakdown by count, critical blocks highlighted, avg time to ready, stale reviews count
- [ ] [GREEN] Implement `WorkspaceHealthSection` with bar chart (or count cards) per state

### OrgHealthSection
- [ ] [RED] Test: active member count, teamless members list (clickable), teams without lead, top loaded owners
- [ ] [GREEN] Implement `OrgHealthSection`

### ProcessHealthSection
- [ ] [RED] Test: override rate %, most skipped validations list, exported count
- [ ] [GREEN] Implement `ProcessHealthSection`

### IntegrationHealthSection
- [ ] [RED] Test: per-config health card, error streak, export counts, link to config detail
- [ ] [GREEN] Implement `IntegrationHealthSection`

### Project Scope Filter
- [ ] [GREEN] Dropdown at top of page: "All projects" + individual project names; updates query param; re-fetches dashboard data

### Loading / Empty / Error
- [ ] [RED] Test: skeletons during fetch, zeros/empty states for new workspace, inline error + retry on 5xx
- [ ] [GREEN] Apply SkeletonLoader to each section, EmptyState for zero-data workspace

---

## Group 8 — Support Tools (`app/admin/support/page.tsx`)

### Acceptance Criteria

WHEN the support tools page loads
THEN each section shows a count badge (e.g., "3 orphaned items")

WHEN "Retry all" is clicked and returns HTTP 429
THEN the button is disabled for 10 minutes and shows a countdown or "Available again in X min" label

WHEN "Retry all" is clicked while Jira config is in `error` state
THEN a warning banner renders above the button: "Jira integration is in error state — retries may fail"

WHEN the orphaned items list renders a suspended owner
THEN the owner's name is displayed with strikethrough styling

WHEN the config-blocked items section renders
THEN items are visually grouped by blocking reason (suspended owner / deleted team in rule / archived project)
AND each group has a header label

## Group 8 — Support Tools (`app/admin/support/page.tsx`)

- [ ] [RED] Test: four sections visible (orphaned items, pending invitations, failed exports, config-blocked items); each shows count badge
- [ ] [GREEN] Implement support tools page with four collapsible sections

### Orphaned Work Items
- [ ] [RED] Test: list with owner name (struck-through if suspended/deleted), reassign button per item
- [ ] [GREEN] Implement orphaned items list with inline `ReassignOwnerForm` (member picker)

### Pending Invitations
- [ ] [RED] Test: list with email, expiry date, "expiring soon" warning badge, resend button
- [ ] [GREEN] Implement pending invitations list

### Failed Exports
- [ ] [RED] Test: list with work item title, error_code, attempt count, retry button (requires RETRY_EXPORTS), "Retry all" button with 429 handling
- [ ] [GREEN] Implement failed exports list with individual and bulk retry
- [ ] [GREEN] "Retry all" shows disabled state for 10 min after last call (429 handling)
- [ ] [GREEN] Warning banner when Jira config is in error state (retrying is pointless)

### Config-Blocked Work Items
- [ ] [RED] Test: list grouped by blocking reason (suspended owner / deleted team in rule / archived project)
- [ ] [GREEN] Implement config-blocked items grouped list
