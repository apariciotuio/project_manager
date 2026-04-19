# Spec: Project Configuration & Context Sources
## US-100 — Select Relevant Context Sources
## US-101 — Save Reusable Context Configurations

**Epic**: EP-10 — Configuration, Projects, Rules & Administration
**Priority**: US-100: Must | US-101: Should
**Dependencies**: EP-00 (workspace bootstrap), EP-08 (teams), US-102/US-103 (rules/routing)

---

## Domain Model

### Project

An organizational unit within a workspace grouping elements, context, rules, and teams.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | |
| `name` | string | Unique within workspace |
| `description` | string or null | |
| `state` | enum | `active`, `archived` |
| `team_ids` | uuid[] | Teams associated with this project |
| `context_preset_id` | uuid or null | Linked reusable context preset |
| `context_sources` | ContextSource[] | Inline sources if no preset |
| `default_template_bindings` | TemplateBinding[] | Per element type default template |
| `created_by` | uuid | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

### ContextSource

A single source of context (repository, system, doc, URL) associated with a project.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `project_id` | uuid or null | Null if part of a preset |
| `preset_id` | uuid or null | Null if directly on project |
| `type` | enum | `repository`, `system`, `documentation`, `connected_project`, `url` |
| `label` | string | Human-readable name |
| `url` | string or null | Link if applicable |
| `description` | string or null | How this source is relevant |
| `active` | bool | |

### ContextPreset (US-101)

A reusable named collection of context sources that can be linked to multiple projects.

| Field | Type | Description |
|---|---|---|
| `id` | uuid | |
| `workspace_id` | uuid | |
| `name` | string | Unique within workspace |
| `description` | string or null | |
| `sources` | ContextSource[] | Template sources |
| `created_by` | uuid | |
| `updated_at` | timestamp | |

### TemplateBinding

Links a template (from template management, future epic) to an element type within a project.

| Field | Type | Description |
|---|---|---|
| `element_type` | enum | |
| `template_id` | uuid | |

---

## US-100: Select Context Sources for a Project

### Create Project

**WHEN** a member with `configure_workspace_rules` capability submits `POST /api/v1/admin/projects` with `{name, description, team_ids[], context_sources[]}`
**THEN** a project is created in `active` state
**AND** the provided context sources are stored linked to the project
**AND** `team_ids` references are validated: any non-existent team ID causes rejection with `422` and `error.code: team_not_found`, listing all invalid IDs
**AND** the audit log records `action: project_created`, `project_id`, `actor`

**WHEN** `name` is not unique within the workspace
**THEN** the request is rejected with `409 Conflict` and `error.code: project_name_taken`

**WHEN** no context sources and no `context_preset_id` are provided
**THEN** the project is created with empty context (valid — system works with minimal config)

---

### Add Context Sources to Project

**WHEN** a member with `configure_project` capability submits `POST /api/v1/admin/projects/{project_id}/context-sources` with `{type, label, url, description}`
**THEN** a context source is added to the project
**AND** the new source is immediately available for AI enrichment and suggestion features
**AND** the audit log records `action: context_source_added`, `project_id`, `source_id`

**WHEN** `type` is outside the allowed enum values
**THEN** rejected with `422` and `error.code: invalid_source_type`

**WHEN** `type = repository` and `url` is not a valid HTTPS URL
**THEN** rejected with `422` and `error.code: invalid_url`

---

### Remove Context Source

**WHEN** a member with `configure_project` capability submits `DELETE /api/v1/admin/projects/{project_id}/context-sources/{source_id}`
**THEN** the source is removed from the project
**AND** existing elements already enriched using that source retain their stored context (no retroactive purge)
**AND** future enrichment requests for elements in this project will no longer include the removed source
**AND** the audit log records `action: context_source_removed`

---

### Replace Project Context Sources in Bulk

**WHEN** a member with `configure_project` capability submits `PUT /api/v1/admin/projects/{project_id}/context-sources` with `{sources: [...]}`
**THEN** the full set of context sources is replaced atomically
**AND** removed sources follow the same "no retroactive purge" rule as individual removal
**AND** the audit log records `action: context_sources_replaced`, `before_count`, `after_count`

---

### Associate Teams with Project

**WHEN** a member with `configure_project` capability submits `PATCH /api/v1/admin/projects/{project_id}` with `{team_ids: [...]}`
**THEN** the team associations are updated
**AND** routing rules referencing this project will immediately use the updated team set for suggestions
**AND** the audit log records `action: project_updated`, `before: {team_ids}`, `after: {team_ids}`

---

### Link Context Preset to Project (US-101)

**WHEN** a member with `configure_project` capability submits `PATCH /api/v1/admin/projects/{project_id}` with `{context_preset_id: uuid}`
**THEN** the project's context is derived from the preset (preset sources + any additional inline sources)
**AND** if the project already had inline context sources, they are preserved alongside preset sources (union, not replacement)
**AND** the audit log records `action: project_preset_linked`, `preset_id`

**WHEN** the preset ID does not exist in the workspace
**THEN** rejected with `422` and `error.code: preset_not_found`

---

### Template Binding per Element Type

**WHEN** a member with `configure_project` capability submits `PATCH /api/v1/admin/projects/{project_id}/template-bindings` with `{element_type, template_id}`
**THEN** when a new element of that type is created in this project, the bound template is pre-applied
**AND** the template binding is a default, not a mandate — users can still clear or change the template
**AND** the audit log records `action: template_binding_updated`

---

### Archive Project

**WHEN** a member with `configure_workspace_rules` capability submits `PATCH /api/v1/admin/projects/{project_id}` with `{state: "archived"}`
**THEN** the project transitions to `archived`
**AND** new elements cannot be created in an archived project
**AND** existing elements in the project retain their state and remain visible/operable until individually resolved
**AND** routing rules scoped to this project are soft-disabled (not deleted)
**AND** an admin alert is queued if any elements in the project have non-terminal state (`count_open_elements`)
**AND** the audit log records `action: project_archived`

**WHEN** a user attempts to create an element in an archived project
**THEN** rejected with `409 Conflict` and `error.code: project_archived`

---

## US-101: Reusable Context Presets

### Create Context Preset

**WHEN** a member with `configure_workspace_rules` capability submits `POST /api/v1/admin/context-presets` with `{name, description, sources[]}`
**THEN** a reusable preset is created
**AND** it is immediately available for linking to any project
**AND** the audit log records `action: context_preset_created`

**WHEN** `name` is not unique within the workspace
**THEN** rejected with `409 Conflict` and `error.code: preset_name_taken`

---

### Update Context Preset

**WHEN** a member with `configure_workspace_rules` capability submits `PATCH /api/v1/admin/context-presets/{preset_id}` with updated `{name, description, sources[]}`
**THEN** the preset is updated
**AND** all projects linked to this preset immediately reflect the updated source set (dynamic binding, not snapshot)
**AND** the audit log records `action: context_preset_updated`, `linked_project_count`

**WHEN** a preset linked to 3+ projects has its sources modified
**THEN** the response includes `{affected_projects_count, affected_project_ids[]}` as informational warning (not a block)

---

### Delete Context Preset

**WHEN** `DELETE /api/v1/admin/context-presets/{preset_id}` is submitted
**AND** no projects are currently linked to the preset
**THEN** the preset is deleted

**WHEN** one or more projects are linked to the preset
**THEN** rejected with `409 Conflict` and `error.code: preset_in_use`
**AND** the response lists `linked_project_ids[]`

---

### List Context Presets

**WHEN** `GET /api/v1/admin/context-presets` is called
**THEN** all workspace presets are returned with `{id, name, description, source_count, linked_project_count}`

---

## Edge Cases

- Project context changes while elements are being enriched: in-flight enrichment jobs use the snapshot of sources at job start time; no race condition on completion.
- A team is deleted that is associated with a project: the `team_ids[]` array on the project has the deleted ID removed automatically; an admin alert is queued.
- An archived project's elements have owners who are later suspended: orphan-owner alert applies normally regardless of project state.
- Two preset updates happen simultaneously: optimistic locking; second update returns `409 Concurrent modification`.
- Workspace has no projects configured: system operates normally; elements are created without project scope; routing returns `null` project-level suggestions.

---

## API Endpoints Summary

| Method | Path | Required Capability |
|---|---|---|
| `POST` | `/api/v1/admin/projects` | `configure_workspace_rules` |
| `GET` | `/api/v1/admin/projects` | `configure_project` or `view_admin_dashboard` |
| `GET` | `/api/v1/admin/projects/{id}` | `configure_project` or `view_admin_dashboard` |
| `PATCH` | `/api/v1/admin/projects/{id}` | `configure_project` |
| `POST` | `/api/v1/admin/projects/{id}/context-sources` | `configure_project` |
| `PUT` | `/api/v1/admin/projects/{id}/context-sources` | `configure_project` |
| `DELETE` | `/api/v1/admin/projects/{id}/context-sources/{source_id}` | `configure_project` |
| `PATCH` | `/api/v1/admin/projects/{id}/template-bindings` | `configure_project` |
| `POST` | `/api/v1/admin/context-presets` | `configure_workspace_rules` |
| `GET` | `/api/v1/admin/context-presets` | `configure_project` or `view_admin_dashboard` |
| `PATCH` | `/api/v1/admin/context-presets/{id}` | `configure_workspace_rules` |
| `DELETE` | `/api/v1/admin/context-presets/{id}` | `configure_workspace_rules` |
