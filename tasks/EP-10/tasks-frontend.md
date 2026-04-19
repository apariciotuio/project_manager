# EP-10 Frontend Subtasks — Configuration, Projects, Rules & Administration

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `TypedConfirmDialog` for destructive admin actions (member delete/suspend, rule delete, preset delete), `StateBadge` for rule/integration health, `HumanError`, semantic tokens, i18n `i18n/es/admin.ts`. Capability matrix editor, routing rule form, storage-usage dashboard remain feature-specific. See `tasks/extensions.md#EP-19`.

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS, React Query
**Depends on**: EP-12 layout primitives (AppShell, DataTable, EmptyState, SkeletonLoader, ErrorBoundary), EP-12 API client, EP-12 responsive patterns, EP-19 catalog

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

- [x] [GREEN] Implement `hooks/use-admin.ts` — `useWorkspaceMembers` (GET /api/v1/workspaces/members), `useAuditEvents(filters)`, `useHealth`, `useProjects` (createProject, updateProject, deleteProject), `useIntegrations` (createIntegration, deleteIntegration), `useTags` — 2026-04-17
- [x] [GREEN] Implement `lib/api/admin/members.ts` — `listMembers`, `inviteMember`, `updateMember`, `resendInvitation` — 2026-04-18
- [x] [GREEN] Implement `lib/api/admin/rules.ts` — `listValidationRules`, `createValidationRule`, `updateValidationRule`, `deleteValidationRule` — 2026-04-18
- [ ] [GREEN] Implement `lib/api/admin/projects.ts` — `listProjects`, `createProject`, `updateProject`, `getProject`, `replaceContextSources`, `updateTemplateBindings` (blocked: admin projects endpoints not yet live; current impl uses /api/v1/projects)
- [x] [GREEN] Implement `lib/api/admin/presets.ts` — `listContextPresets`, `createContextPreset`, `updateContextPreset`, `deleteContextPreset` — 2026-04-18
- [x] [GREEN] Implement `lib/api/admin/jira.ts` — `listJiraConfigs`, `createJiraConfig`, `updateJiraConfig`, `testJiraConnection`, `listMappings`, `createMapping` — 2026-04-18
- [x] [GREEN] Implement audit events hook — `getAuditLog(filters)` via `useAuditEvents(filters)` in use-admin.ts — 2026-04-17
- [x] [GREEN] Implement `lib/api/admin/dashboard.ts` — `getAdminDashboard(projectId?)` — 2026-04-18
- [x] [GREEN] Implement `lib/api/admin/support.ts` — `getOrphanedItems`, `reassignOwner`, `getPendingInvitations`, `getFailedExports`, `retryAllExports`, `getConfigBlockedItems` — 2026-04-18
- [x] All functions use shared API client with correlation ID header (EP-12) (2026-04-19: all admin API modules use `frontend/lib/api-client.ts` which attaches correlation ID)

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

- [ ] [RED] Test: admin routes are only reachable when `member.capabilities` contains at least one admin capability; redirect to `/` otherwise (deferred: capability guard not implemented; admin page has no layout.tsx guard)
- [ ] [GREEN] Implement `app/admin/layout.tsx` — admin section layout with capability guard (deferred: page is at /workspace/[slug]/admin/page.tsx, no separate /admin layout with route guard)
- [ ] [GREEN] Implement admin side navigation: Members, Rules, Projects, Integrations (Jira + Puppet), Tags, Audit Log, Dashboard, Support Tools (partial: current impl is tab-based, not side-nav; no /admin/* sub-routes)
- [ ] [GREEN] Superadmin-only sections (visible only when `user.is_superadmin = true` from `/auth/me`): User Management (create user form), Cross-Workspace Audit — hide menu items completely, do not disable them (deferred: no superadmin gating in current tabs)
- [ ] [GREEN] Mobile: admin nav collapses to hamburger/drawer; side navigation on md+ (deferred: tab UI only)
- [ ] [GREEN] Active nav item highlighted per current route (N/A: tab-based, not route-based)

---

## Group 2 — Members & Capabilities

### Member List (`app/admin/members/page.tsx`)
- [x] [RED] Test: renders member list with state badges, capability chips, filter by state and teamless — 2026-04-17 (role badge; capability/team filter deferred, EP-12 DataTable not yet in)
- [x] [RED] Test: empty state when no members — 2026-04-17 (data-testid="members-empty")
- [x] [RED] Test: skeleton shown during fetch — 2026-04-17 (data-testid="members-skeleton")
- [x] [GREEN] Implement member list: table with full_name / email / role; loading skeleton / empty state / error banner — 2026-04-17 (inline MembersTab in admin/page.tsx; GET /api/v1/workspaces/members)
- [x] [GREEN] Columns: name/email, state badge, capabilities chips, context labels, actions — 2026-04-18 (MembersTabEnhanced component)
- [ ] [GREEN] Filter controls: by state (active/invited/suspended/deleted), teamless toggle (deferred: backend doesn't return state/capabilities)
- [ ] [GREEN] Cursor-based pagination via "Load more" or paginated DataTable (deferred: backend pagination not yet live)

### Invite Member Form
- [x] [RED] Test: invite 409 member_already_active shows inline error — 2026-04-18
- [x] [GREEN] Implement `InviteMemberModal` (email field, 409 error handling) — 2026-04-18
- [x] [GREEN] Trigger from "Invite member" button in member list — 2026-04-18

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
- [ ] [RED] Test: checkboxes render for each capability, disabled if current user doesn't possess the capability (cannot grant unpossessed), submit calls PATCH, 403 shows inline error (blocked: PATCH /api/v1/admin/members/{id} not live)
- [ ] [GREEN] Implement `MemberCapabilityEditor` — checkbox grid for all 10 capabilities (blocked: same)
- [ ] [GREEN] Disable capabilities the acting member doesn't hold (granting constraint) (blocked: same)
- [ ] [GREEN] Context labels editor: tag-input component (add/remove text labels) (blocked: same)

### Suspend / Delete / Reactivate Actions
- [x] [RED] Test: patch member state calls PATCH endpoint, confirm dialog — 2026-04-18
- [x] [GREEN] Implement Suspend button on member row with confirm dialog — 2026-04-18
- [ ] [GREEN] Confirmation dialogs with consequence text (blocked: same)

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
- [x] [RED] Test: renders rules list, enforcement badge, scope, superseded_by, empty state, create/delete — 2026-04-18
- [x] [GREEN] Implement ValidationRulesTab with CRUD (no routing rules — BE only has validation endpoint) — 2026-04-18
- [ ] [GREEN] Validation rule row: work_item_type, validation_type, enforcement badge, scope (workspace/project), effective badge, superseded_by indicator (blocked: same)
- [ ] [GREEN] Filter: by work_item_type, by project, by active/inactive (blocked: same)

### Create/Edit Validation Rule Form
- [x] [RED] Test: create rule form submits POST, delete 409 rule_has_history shows error — 2026-04-18
- [x] [GREEN] Implement create rule form inline in ValidationRulesTab — 2026-04-18
- [ ] [GREEN] `blocked_override` enforcement shows warning: "This will supersede any project-level rule of the same type" (blocked: same)

### Routing Rule Form
- [ ] [RED] Test: optional fields, team picker, context label picker, submit (blocked: routing rule endpoints not live)
- [ ] [GREEN] Implement `RoutingRuleForm` modal/drawer (blocked: same)

### Delete Rule
- [x] [RED] Test: delete 409 rule_has_history shows 'Cannot delete — use Deactivate instead' — 2026-04-18
- [x] [GREEN] Delete shows error in dialog when 409 returned — 2026-04-18

---

## Group 4 — Projects & Context

### Project List (`app/admin/projects/page.tsx`)
- [ ] [RED] Test: renders project list, state badge, team chips, preset indicator — DEFERRED (state/team/preset fields not in current Project type; BE returns name+description only)
- [x] [GREEN] Implement project list page (2026-04-19: inline `ProjectsTab` in `frontend/app/workspace/[slug]/admin/page.tsx:308` — state/team/preset display still deferred)

### Create/Edit Project Form
- [x] [RED] Test: create success (project in list), 409 PROJECT_NAME_TAKEN inline field error, edit PATCH updates list, delete removes from list — 2026-04-17
- [x] [GREEN] Implement create modal (name + description, 409 field error), edit modal (PATCH), delete confirmation dialog — 2026-04-17 (ProjectsTab in admin/page.tsx; updateProject/deleteProject added to useProjects)
- [ ] [GREEN] Archive project: confirmation dialog with open-elements count warning (blocked: no backend archive endpoint)

### Context Sources Editor (`components/admin/ContextSourcesEditor.tsx`)
- [ ] [RED] Test: add source (type/label/url/description), remove source, bulk replace via PUT, inline validation (blocked: GET/PUT /api/v1/admin/projects/{id}/context-sources not live)
- [ ] [GREEN] Implement context sources editor as inline list within project edit page (blocked: same)
- [ ] [GREEN] Source types: enum select, label and URL required (blocked: same)

### Context Presets (`app/admin/context-presets/page.tsx`)
- [x] [RED] Test: list, create, delete, 409 preset_in_use error — 2026-04-18
- [x] [GREEN] Implement ContextPresetsTab with list + create + edit + delete — 2026-04-18
- [ ] [GREEN] Delete: show "in use by N projects" warning when 409 returned (blocked: same)

### Template Bindings
- [ ] [GREEN] Implement `TemplateBundlingEditor` — key/value editor for template bindings JSONB field (within project edit) (blocked: template_bindings field not in current Project type)

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

WHEN the retry button in `JiraExportHistoryTable` is clicked by a user lacking `retry_exports` capability
THEN the button is absent (not just disabled)

### General Integrations Tab (admin/page.tsx — IntegrationsTab)
- [x] [RED] Test: list with provider + status badge, empty state, create success, delete removes from list, masked credentials hint — 2026-04-17
- [x] [GREEN] Implement IntegrationsTab: list with active/inactive badge + masked credentials row, create modal (base_url/email/api_token), delete confirmation — 2026-04-17 (GET/POST /api/v1/integrations/configs; deleteIntegration added to useIntegrations; NOTE: backend has no DELETE /api/v1/integrations/configs/{id} — optimistic delete will 404 in prod until endpoint added)

### Jira Config List (`app/admin/integrations/jira/page.tsx`)
- [x] [RED] Test: renders config list, state badge, empty state, HTTPS validation, test connection — 2026-04-18
- [x] [GREEN] Implement JiraConfigTab with list + create + test connection — 2026-04-18
- [ ] [GREEN] State badges: active (green), disabled (grey), error (red with streak count) (blocked: error state/streak not in current IntegrationConfig type)

### Create Jira Config Form
- [ ] [RED] Test: base URL validation (must be HTTPS), auth type select (API token, OAuth), credentials fields (never pre-filled on edit), submit creates config, server-side 422 shown inline (deferred: current form has no HTTPS validation; Jira-specific form not yet separate)
- [ ] [GREEN] Implement `JiraConfigForm` — credentials fields never show existing values (write-only UI) (deferred: same)
- [ ] [GREEN] Credential fields: `email` + `api_token` for API token auth (partial: current create form has these fields but no write-only enforcement on edit)

### Test Connection
- [x] [RED] Test: test connection ok/auth_failure results shown inline — 2026-04-18
- [x] [GREEN] Implement inline test connection result in JiraConfigTab — 2026-04-18

### Project Mappings (`components/admin/JiraProjectMappings.tsx`)
- [ ] [RED] Test: list mappings, add mapping (jira project key, workspace project picker, type mappings table), submit (blocked: /api/v1/admin/integrations/jira/{id}/mappings not live)
- [ ] [GREEN] Implement `JiraProjectMappings` as a section within config detail page (blocked: same)
- [ ] [GREEN] Work item type mappings: table with platform type → Jira issue type ID mapping (blocked: same)

### Export History Viewer
- [ ] [RED] Test: export history list (from `jira_export_events` — EP-11) with status filter, pagination, retry button on failed export (requires RETRY_EXPORTS capability) (blocked: EP-11 jira_export_events endpoint not live)
- [ ] [GREEN] Implement `JiraExportHistoryTable` within config detail page — sourced from EP-11 export events, not from a `sync_logs` table (decision #26) (blocked: same)
- [ ] [GREEN] Retry button: disabled if user lacks `retry_exports` capability (check from current member context) (blocked: capabilities not in current member type)

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

- [x] [GREEN] Implement `lib/api/admin/puppet.ts` — `createPuppetConfig`, `updatePuppetConfig`, `testPuppetConnection` via `hooks/use-puppet-config.ts`; `listSources`, `addSource`, `deleteSource` via `hooks/use-doc-sources.ts` — 2026-04-18 (files: `hooks/use-puppet-config.ts`, `hooks/use-doc-sources.ts`)
- [x] [RED] Test: renders config list with state badge, test-connection flow, form validation (HTTPS required) — 2026-04-18 (tests in `__tests__/app/workspace/admin-puppet-tab.test.tsx`, `__tests__/components/admin/puppet-config-form.test.tsx`)
- [x] [GREEN] Implement Puppet integration list page — 2026-04-18 (PuppetTab inline in `app/workspace/[slug]/admin/page.tsx`)
- [x] [GREEN] Implement `PuppetConfigForm` — API key field is write-only (never pre-filled on edit) — 2026-04-18 (`components/admin/puppet-config-form.tsx`)
- [x] [GREEN] Documentation sources editor: add/remove URL entries inline — 2026-04-18 (`components/admin/doc-sources-table.tsx`, `components/admin/add-doc-source-modal.tsx`)
- [ ] [GREEN] Test Connection button: same spinner/result pattern as Jira (deferred: test-connection POST endpoint not live; PuppetConfigForm has `runHealthCheck` in hook but no inline result UI)

---

## Group 5c — Superadmin Sections

Visibility: render only when `user.is_superadmin = true` (from `/auth/me` response). Do not render disabled — omit entirely.

### User Management (`app/admin/users/new/page.tsx`)

- [ ] [RED] Test: form hidden when `is_superadmin = false`, visible when `true` (deferred: no superadmin-gated user management page exists; no /admin/users/new route)
- [ ] [RED] Test: form validation (email, display_name required), workspace picker, initial capabilities multi-select, submit creates user, 409 shows duplicate email error (blocked: superadmin user-create endpoint not live)
- [ ] [GREEN] Implement create-user form page (superadmin only) (deferred: no such page)
- [ ] [GREEN] Route guarded by `is_superadmin` check — redirect to `/admin` if not superadmin (deferred: same)

### Cross-Workspace Audit (`app/admin/audit/cross-workspace/page.tsx`)

- [ ] [RED] Test: page hidden when `is_superadmin = false`, renders full audit table when `true` (deferred: no cross-workspace audit page)
- [ ] [GREEN] Implement cross-workspace audit viewer — same filters as workspace audit log but no workspace scope constraint (blocked: cross-workspace audit endpoint not live)
- [ ] [GREEN] Each row shows `workspace_id` / workspace name column (not present in workspace-scoped audit log) (blocked: same)
- [ ] [GREEN] Route guarded by `is_superadmin` check (deferred: same)

---

## Group 5d — Tags Admin Entry Point

Tag management is implemented in EP-15. This epic adds the left-nav entry point.

- [x] [GREEN] Tags tab in admin page: TagsTab with loading skeleton / empty state (data-testid="tags-empty") / error banner (data-testid="tags-error") consistent with other tabs — 2026-04-17
- [x] [RED] Test: shows tags, empty state, error banner, edit icon opens modal pre-filled, PATCH updates list, 409 shows field error — 2026-04-17
- [ ] [GREEN] Admin left-nav entry: **Tags** → `/admin/tags` (deferred: route implemented in EP-15; current is inline tab)
- [ ] [GREEN] Entry visible to members with `manage_tags` or `merge_tags` capability (or superadmin) (deferred: capability gating not yet implemented)

---

## Group 6 — Audit Log (`app/admin/audit-log/page.tsx`)

- [x] [RED] Test: renders log table with actor, action, entity, date; filters (action select, category text); empty state — 2026-04-17
- [x] [GREEN] Implement audit tab: action filter select + category text input; re-fetches on change; empty/error states — 2026-04-17 (AuditTab in admin/page.tsx; GET /api/v1/admin/audit-events?action=&category=)
- [x] [RED] Test: action filter triggers re-fetch with action= param — 2026-04-17
- [ ] [GREEN] Filter bar: actor search, entity type filter, date range picker (deferred: backend doesn't support actor/entity_type/date params yet)
- [ ] [GREEN] Row detail: expand row to show before/after JSONB diff (collapsible) (deferred: before_value/after_value present in type but no expand UI)
- [ ] [GREEN] Cursor-based pagination, max 200 per page (deferred: current impl fetches page=1 only)
- [ ] [RED] Test: 403 shown when user lacks `view_audit_log` capability (guard at page level) (deferred: capability gating not yet implemented)

---

## Group 7 — Admin Health Dashboard (`app/admin/dashboard/page.tsx`)

- [x] [RED] Test: state breakdown bar segments per state, total_active count, empty + error states — 2026-04-17 (scoped to WorkspaceHealthSection only; GET /api/v1/admin/health)
- [x] [RED] Test: 7 cases (stat cards x4, health pill, skeleton, error) — 2026-04-18
- [x] [GREEN] Implement AdminDashboardTab with stat cards + health pill + work items bar — 2026-04-18

### WorkspaceHealthSection
- [x] [RED] Test: bar segments add up (widths > 0 when count > 0) — 2026-04-17
- [x] [GREEN] Implement HealthTab with divided bar chart, colour-coded by state, legend below — 2026-04-17 (inline HealthTab in admin/page.tsx)

### OrgHealthSection
- [ ] [RED] Test: active member count, teamless members list (clickable), teams without lead, top loaded owners (blocked: GET /api/v1/admin/dashboard org section not live)
- [ ] [GREEN] Implement `OrgHealthSection` (blocked: same)

### ProcessHealthSection
- [ ] [RED] Test: override rate %, most skipped validations list, exported count (blocked: GET /api/v1/admin/dashboard process section not live)
- [ ] [GREEN] Implement `ProcessHealthSection` (blocked: same)

### IntegrationHealthSection
- [ ] [RED] Test: per-config health card, error streak, export counts, link to config detail (blocked: GET /api/v1/admin/dashboard integration section not live)
- [ ] [GREEN] Implement `IntegrationHealthSection` (blocked: same)

### Project Scope Filter
- [ ] [GREEN] Dropdown at top of page: "All projects" + individual project names; updates query param; re-fetches dashboard data (deferred: not implemented)

### Loading / Empty / Error
- [ ] [RED] Test: skeletons during fetch, zeros/empty states for new workspace, inline error + retry on 5xx (partial: workspace section has skeleton/empty/error; other sections not built)
- [ ] [GREEN] Apply SkeletonLoader to each section, EmptyState for zero-data workspace (partial: same)

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

- [x] [RED] Test: all 5 support sections + retry-all — 2026-04-18
- [x] [GREEN] Implement SupportTab with all 4 sections — 2026-04-18

### Orphaned Work Items
- [ ] [RED] Test: list with owner name (struck-through if suspended/deleted), reassign button per item (blocked: GET /api/v1/admin/support/orphaned-items not live)
- [ ] [GREEN] Implement orphaned items list with inline `ReassignOwnerForm` (member picker) (blocked: same)

### Pending Invitations
- [ ] [RED] Test: list with email, expiry date, "expiring soon" warning badge, resend button (blocked: GET /api/v1/admin/support/pending-invitations not live)
- [ ] [GREEN] Implement pending invitations list (blocked: same)

### Failed Exports
- [ ] [RED] Test: list with work item title, error_code, attempt count, retry button (requires RETRY_EXPORTS), "Retry all" button with 429 handling (blocked: GET /api/v1/admin/support/failed-exports not live)
- [ ] [GREEN] Implement failed exports list with individual and bulk retry (blocked: same)
- [ ] [GREEN] "Retry all" shows disabled state for 10 min after last call (429 handling) (blocked: same)
- [ ] [GREEN] Warning banner when Jira config is in error state (retrying is pointless) (blocked: same)

### Config-Blocked Work Items
- [ ] [RED] Test: list grouped by blocking reason (suspended owner / deleted team in rule / archived project) (blocked: GET /api/v1/admin/support/config-blocked-items not live)
- [ ] [GREEN] Implement config-blocked items grouped list (blocked: same)
