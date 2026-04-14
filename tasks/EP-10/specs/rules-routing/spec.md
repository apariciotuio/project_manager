# Spec: Validation Rules, Routing Rules & Context Labels
## US-102 — Configure Participants, Teams, and Validation Rules
## US-103 — Use Roles as Contextual Labels and Routing Hints

**Epic**: EP-10 — Configuration, Projects, Rules & Administration
**Priority**: Must
**Dependencies**: EP-00 (identity), EP-08 (teams), US-100 (project context)

---

## Domain Model

### Validation Rule

A rule that declares which validations are required or recommended for elements of a given type, optionally scoped to a project.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | Always set |
| `project_id` | uuid or null | Null = workspace-level (global) |
| `element_type` | enum | `feature`, `bug`, `spike`, `initiative`, `task` |
| `validation_type` | enum | `tech`, `qa`, `business`, `product`, `cross` |
| `enforcement` | enum | `required`, `recommended`, `blocked_override` |
| `suggested_teams` | uuid[] | Teams suggested as validators for this rule |
| `suggested_context_labels` | string[] | Context labels suggested for validators |
| `order_hint` | int | Suggested sequence position |
| `active` | bool | Soft-disable without deletion |
| `created_by` | uuid | |
| `updated_at` | timestamp | |

### Routing Rule

A rule that suggests team, owner, or template for elements based on type and/or project.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | |
| `project_id` | uuid or null | Null = workspace-level |
| `element_type` | enum or null | Null = applies to all types |
| `suggested_team_id` | uuid or null | |
| `suggested_owner_context_label` | string or null | e.g. `product` |
| `suggested_template_id` | uuid or null | |
| `active` | bool | |
| `created_by` | uuid | |
| `updated_at` | timestamp | |

### Rule Precedence

```
project-level rule  >  workspace-level rule
EXCEPT:
  enforcement = "blocked_override"  → workspace-level, always applies, cannot be overridden by project
```

When both a project-level and workspace-level rule exist for the same `(element_type, validation_type)`:
- Project-level wins for `required` and `recommended` rules.
- `blocked_override` rules at workspace level apply regardless and cannot be overridden.

---

## US-102: Configure Validation Rules

### Create Validation Rule (Workspace Level)

**WHEN** a member with `configure_workspace_rules` capability submits `POST /api/v1/admin/rules/validation` with `{element_type, validation_type, enforcement, suggested_teams[], suggested_context_labels[], order_hint}` and no `project_id`
**THEN** a validation rule is created scoped to the workspace (`project_id = null`)
**AND** the rule is immediately active and applies to all new elements matching the type
**AND** the audit log records `action: validation_rule_created`, `entity: validation_rule`, `actor`, `rule_id`, `scope: workspace`

**WHEN** a rule already exists for the same `(workspace_id, project_id=null, element_type, validation_type)`
**THEN** the request is rejected with `409 Conflict` and `error.code: rule_already_exists`
**AND** the response includes the existing rule ID so the caller can update instead

---

### Create Validation Rule (Project Level)

**WHEN** a member with `configure_project` capability submits `POST /api/v1/admin/rules/validation` with `{project_id, element_type, validation_type, enforcement, ...}`
**THEN** a validation rule is created scoped to that project
**AND** if a workspace-level rule exists for the same `(element_type, validation_type)` with `enforcement = blocked_override`, the project rule is rejected with `409 Conflict` and `error.code: global_blocker_in_effect`
**AND** otherwise the project rule overrides the workspace rule for elements in that project
**AND** the audit log records `action: validation_rule_created`, `scope: project`, `project_id`

---

### Update Validation Rule

**WHEN** a member with the appropriate scoped capability submits `PATCH /api/v1/admin/rules/validation/{rule_id}` with partial update fields
**THEN** only the provided fields are updated (partial update, not replacement)
**AND** `enforcement` may be changed from `required` to `recommended` or vice versa
**AND** changing a workspace rule to `blocked_override` triggers a check: any existing project-level rules for the same `(element_type, validation_type)` are flagged as `superseded` and a warning is returned in the response
**AND** the audit log records `action: validation_rule_updated`, `before: {old_values}`, `after: {new_values}`

---

### Deactivate / Delete Validation Rule

**WHEN** a member with the appropriate capability submits `PATCH /api/v1/admin/rules/validation/{rule_id}` with `{active: false}`
**THEN** the rule is soft-disabled and no longer applied to new elements
**AND** existing elements already in review are not retroactively affected
**AND** the audit log records `action: validation_rule_deactivated`

**WHEN** `DELETE /api/v1/admin/rules/validation/{rule_id}` is submitted
**THEN** the rule is hard-deleted only if no element has ever had it applied (zero historical references)
**AND** if historical references exist, the request is rejected with `409 Conflict` and `error.code: rule_has_history`
**AND** the caller is advised to use `active: false` instead

---

### List Validation Rules

**WHEN** `GET /api/v1/admin/rules/validation` is called with optional `?project_id=&element_type=&active=`
**THEN** rules are returned with effective precedence resolved: each entry includes `effective: true|false` indicating whether a project override or global blocker makes it the active rule
**AND** the response is grouped by `element_type` for readability

**WHEN** `?project_id=X` is provided
**THEN** both workspace-level and project-level rules for that project are returned, with each rule annotated with `scope: workspace|project` and `superseded_by: rule_id|null`

---

## US-102: Configure Routing Rules

### Create Routing Rule

**WHEN** a member with `configure_workspace_rules` or `configure_project` capability (matching scope) submits `POST /api/v1/admin/rules/routing` with `{element_type, project_id, suggested_team_id, suggested_owner_context_label, suggested_template_id}`
**THEN** a routing rule is created
**AND** at least one of `suggested_team_id`, `suggested_owner_context_label`, or `suggested_template_id` must be non-null, otherwise reject with `422` and `error.code: routing_rule_empty`
**AND** the audit log records `action: routing_rule_created`

**WHEN** `suggested_team_id` references a team that does not exist in the workspace
**THEN** the request is rejected with `422 Unprocessable Entity` and `error.code: team_not_found`

---

### Routing Suggestion Resolution

**WHEN** a member creates a new element of type `T` in project `P`
**THEN** the routing engine evaluates rules in order: project-level first, then workspace-level
**AND** returns `{suggested_team_id, suggested_owner_context_label, suggested_template_id}` as non-binding suggestions in the element creation response
**AND** if no routing rule matches, returns `null` suggestions (system works without routing rules configured)

**WHEN** a routing suggestion is overridden by the user (different team/owner/template selected)
**THEN** the override is recorded on the element (`routing_override: true`) for health dashboard metrics
**AND** no block or warning is shown — routing suggestions are always advisory

---

### Validator Suggestions During Review Request

**WHEN** a member triggers a review request on element `E`
**THEN** the system queries validation rules active for `(element_type, project)` with the project-first precedence
**AND** for each active required/recommended rule, the system resolves suggested validators by:
  1. Members whose context labels intersect `suggested_context_labels`
  2. Members belonging to `suggested_teams`
  3. Union of both, deduplicated
**AND** suspended or deleted members are excluded from suggestions
**AND** the response includes `{required_validations[], suggested_validators_per_validation[]}`

---

## US-103: Context Labels vs Operational Permissions

### The Separation Rule

**WHEN** a member is assigned context labels (`product`, `tech`, `business`, `qa`)
**THEN** those labels are stored in `workspace_member.context_labels[]`
**AND** they influence: routing suggestions, validator suggestions, view filters, dashboard segmentation
**AND** they do NOT grant any operational capabilities (cannot invite members, configure rules, etc.)

**WHEN** a routing rule references `suggested_owner_context_label: "product"`
**THEN** only members with `context_labels` containing `"product"` are suggested as owners
**AND** this has no bearing on whether those members hold any admin capability

---

### Context Label CRUD for Members

**WHEN** `PATCH /api/v1/admin/members/{id}/context-labels` is called with `{labels: ["tech", "qa"]}`
**THEN** the full label set is replaced (not merged) with the provided array
**AND** an empty array `[]` is valid and removes all labels

**WHEN** labels are updated for a member who is a validator on open review requests
**THEN** existing validator assignments are preserved (label change is not retroactive)
**AND** future routing suggestions for new reviews will reflect the updated labels

---

### Routing Suggestion Without Rules

**WHEN** no routing rules are configured for a workspace
**THEN** the system returns `null` suggestions for all elements
**AND** no error occurs — the system operates normally without routing rules
**AND** the health dashboard notes "no routing rules configured" as informational, not critical

---

## Edge Cases

- Project changes validation rules while elements are in-flight: only new review requests are affected; existing open reviews retain the validation set at time of request.
- Two admins simultaneously update the same rule: optimistic locking (version field) detects conflict; second write returns `409` with `error.code: concurrent_modification`.
- A team referenced in a routing rule is deleted: the routing rule's `suggested_team_id` is set to null and a workspace admin alert is queued (`orphaned_routing_rule`).
- Element type `spike` has no validation rules configured: system applies zero required validations — element can reach `ready` without formal reviews.
- Context label `product` is assigned to a member who also has `configure_project` capability: both are independent; routing uses the label, admin operations use the capability.

---

## API Endpoints Summary

| Method | Path | Required Capability |
|---|---|---|
| `POST` | `/api/v1/admin/rules/validation` | `configure_workspace_rules` or `configure_project` (by scope) |
| `GET` | `/api/v1/admin/rules/validation` | `configure_workspace_rules` or `configure_project` |
| `PATCH` | `/api/v1/admin/rules/validation/{id}` | matching scoped capability |
| `DELETE` | `/api/v1/admin/rules/validation/{id}` | matching scoped capability |
| `POST` | `/api/v1/admin/rules/routing` | `configure_workspace_rules` or `configure_project` (by scope) |
| `GET` | `/api/v1/admin/rules/routing` | `configure_workspace_rules` or `configure_project` |
| `PATCH` | `/api/v1/admin/rules/routing/{id}` | matching scoped capability |
| `DELETE` | `/api/v1/admin/rules/routing/{id}` | matching scoped capability |
