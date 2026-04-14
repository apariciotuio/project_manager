# Templates & Header Specs — EP-02

> **Resolved 2026-04-14** (decisions_pending.md #16): Templates are JSON-schema typed and organized in three layers. Layers 1 and 2 are code-immutable. Only Layer 3 (per-type concrete templates) is editable by a Workspace Admin through the admin UI.

## Overview — Three-Layer Template Model

### Layer 1 — Universal Sections (immutable, code-owned)

Every template contains the same eight universal sections. These are locked in code. Admins cannot add, remove, or reorder them.

1. `contexto` — Context / background.
2. `objetivo` — Objective.
3. `alcance` — Scope (in / out of scope).
4. `criterios` — Acceptance criteria.
5. `dependencias` — Dependencies on other items / external systems.
6. `validaciones` — Validation checklist.
7. `desglose` — Task / subtask breakdown.
8. `ownership` — Owner + responsible team + stakeholders.

### Layer 2 — Field Type Catalogue (immutable, code-owned)

A closed catalogue of field types any template field can be. Each field type has a fixed JSON-schema shape with `required`, `prefill`, `help_text`, and `validation` metadata.

| Type | Semantics |
|---|---|
| `text` | Multi-line markdown. |
| `string` | Single-line string. |
| `enum` | Single-select from a list. |
| `multi_enum` | Multi-select from a list. |
| `date` | ISO-8601 date. |
| `date_range` | Start + end date. |
| `duration` | ISO-8601 duration (e.g. P3D). |
| `reference` | Work-item reference (single). |
| `reference_list` | Work-item references (many). |
| `user_reference` | Single user (workspace member). |
| `user_list` | Many users. |
| `attachment_list` | File attachment list (see EP-16). |

Every Layer-3 field declares: `id`, `type` (from catalogue above), `label`, `required: bool`, `prefill` (default value or expression), `help_text`, `validation` (optional — min/max/pattern/allowed values).

### Layer 3 — Per-Type Concrete Templates (editable by Workspace Admin)

One template per work-item type. Each template is a JSON document binding concrete fields (Layer 2 types) to the eight universal sections (Layer 1).

Built-in templates ship for: `bug`, `story`, `spike`, `milestone`, `idea`, `mejora`, `tarea`, `iniciativa`, `cambio`, `requisito`.

Workspace Admins can customize the field list within each universal section (add/remove optional fields, change `required`, adjust `prefill`, update `help_text`). They cannot change Layers 1 or 2.

---

## Template JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["id", "work_item_type", "version", "sections"],
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "work_item_type": {
      "type": "string",
      "enum": ["idea","bug","mejora","tarea","iniciativa","spike","cambio","requisito","milestone","story"]
    },
    "version": { "type": "integer", "minimum": 1 },
    "sections": {
      "type": "object",
      "required": ["contexto","objetivo","alcance","criterios","dependencias","validaciones","desglose","ownership"],
      "additionalProperties": false,
      "properties": {
        "contexto":     { "$ref": "#/$defs/section" },
        "objetivo":     { "$ref": "#/$defs/section" },
        "alcance":      { "$ref": "#/$defs/section" },
        "criterios":    { "$ref": "#/$defs/section" },
        "dependencias": { "$ref": "#/$defs/section" },
        "validaciones": { "$ref": "#/$defs/section" },
        "desglose":     { "$ref": "#/$defs/section" },
        "ownership":    { "$ref": "#/$defs/section" }
      }
    }
  },
  "$defs": {
    "section": {
      "type": "object",
      "required": ["fields"],
      "properties": {
        "fields": {
          "type": "array",
          "items": { "$ref": "#/$defs/field" }
        }
      }
    },
    "field": {
      "type": "object",
      "required": ["id","type","label","required"],
      "properties": {
        "id":        { "type": "string", "pattern": "^[a-z][a-z0-9_]*$" },
        "type":      { "enum": ["text","string","enum","multi_enum","date","date_range","duration","reference","reference_list","user_reference","user_list","attachment_list"] },
        "label":     { "type": "string" },
        "required":  { "type": "boolean" },
        "prefill":   {},
        "help_text": { "type": "string" },
        "validation":{ "type": "object" }
      }
    }
  }
}
```

---

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/templates?type=<type>` | workspace member | Resolves active template for `type` in current workspace (workspace override OR built-in default). |
| GET | `/api/v1/templates` | workspace member | List all active templates for current workspace. |
| POST | `/api/v1/templates` | `manage_templates` | Create a Layer-3 template override. Rejects structural changes that would violate Layer 1 or Layer 2. |
| PATCH | `/api/v1/templates/:id` | `manage_templates` | Edit Layer-3 fields, prefills, help_text, required flags. |
| DELETE | `/api/v1/templates/:id` | `manage_templates` | Remove workspace override; system default re-applies. |

All mutations validate the payload against the JSON schema above. Structural violations (missing universal section, unknown field `type`, malformed `id`) return HTTP 422 with the JSON-schema error path.

---

## Scenario: Resolving the active template for a type

WHEN a user selects `work_item_type = bug` during capture
THEN the backend resolves the active template by `workspace_id + work_item_type`:
  - If a Layer-3 override exists for the workspace, return it.
  - Otherwise return the code-shipped default template.
AND the frontend renders the form driven by the JSON schema of the returned template.

---

## Scenario: Template pre-population preserves `original_input`

WHEN a draft is created from free-form text
THEN `work_items.original_input` is stored verbatim.
AND the structured fields are pre-filled from both the original text (gap detection / LLM fill) and the template `prefill` values.
AND if the user later clears a field, `original_input` remains intact.

---

## Scenario: Admin edits a Layer-3 template

WHEN a Workspace Admin submits PATCH /api/v1/templates/:id modifying Layer 3 (adds an optional field under `alcance`, removes an optional field from `criterios`)
THEN the update is applied.
AND an audit event `template.updated` is emitted with `{before_value, after_value, fields_changed[]}`.

---

## Scenario: Admin attempts to remove a universal section

WHEN a Workspace Admin submits a PATCH whose `sections` object omits `desglose`
THEN the server rejects with HTTP 422, error code `TEMPLATE_STRUCTURE_IMMUTABLE`.
AND no change is persisted.

---

## Scenario: Admin attempts to use an unknown field type

WHEN a Workspace Admin POSTs a template with a field of `type = "rating"` (not in Layer 2)
THEN the server rejects with HTTP 422, error code `TEMPLATE_FIELD_TYPE_INVALID`, pointing to the offending JSON path.

---

## Scenario: Non-admin template mutation

WHEN a workspace member without `manage_templates` capability sends POST or PATCH
THEN the server returns HTTP 403, error code `FORBIDDEN`.

---

## Scenario: Unauthenticated template fetch

WHEN GET /api/v1/templates is called without a valid JWT
THEN the server returns HTTP 401.

---

## Scenario: Existing drafts are snapshot-bound to their template

WHEN a draft was created against template version `v1`
AND an admin later updates the template to `v2`
THEN existing drafts keep rendering against their snapshot (`work_items.template_id` references the version in effect at creation).
AND new drafts use `v2`.

---

## US-023: Functional Header from Creation

### Overview

From the moment a work item exists (even in `draft` state), a persistent header is visible on the detail view. The header shows: type badge, title, state chip, owner avatar + name, completeness score bar, and a "next step" indicator. These are computed and served with every GET /work-items/{id} response. No separate endpoint needed.

### Scenario: Header visible immediately after creation

WHEN a work item is created (POST /work-items returns 201)
THEN the response payload includes the full header block:
  - `type` (enum value + display label)
  - `title`
  - `state` = `draft`
  - `owner.id`, `owner.display_name`, `owner.avatar_url`
  - `completeness_score` (0–100, granular per decisions_pending.md #19)
  - `derived_state` (materialized: `in_progress` | `blocked` | `ready` | null)
AND the frontend renders these immediately without a second fetch.

### Scenario: Header reflects current state after transition

WHEN a state transition occurs (POST /work-items/{id}/transitions)
THEN the GET /work-items/{id} response returns updated `state` and `derived_state`.
AND the header chip updates to reflect the new state.

### Scenario: Completeness score as percentage bar

WHEN a work item is fetched
THEN `completeness_score` is an integer 0–100.
AND the frontend renders a visual progress bar.
AND the score updates as the user fills fields (optimistic).

### Scenario: Owner always shown from creation

WHEN a work item is fetched
THEN `owner` is always populated (defaults to `created_by` at creation).
AND if the owner's workspace membership is suspended, `owner.suspended = true` is present.
AND the header shows a warning indicator when the owner is suspended.

### Scenario: Next step indicator when completeness is low

WHEN `completeness_score < 30`
THEN the header shows a "next step" hint computed from the highest-weight missing universal section or required field.

### Scenario: Derived state shown as secondary indicator

WHEN `derived_state = blocked`
THEN the header shows a blocking indicator alongside the primary state chip.
AND WHEN `derived_state = ready` AND `state = draft` THEN the header shows a "ready to advance" affordance.

### Scenario: Header on a deleted (soft-deleted) item

WHEN a work item has been soft-deleted (`deleted_at IS NOT NULL`)
THEN GET /work-items/{id} returns HTTP 404.
AND no header is rendered.

### Scenario: Owner avatar fallback

WHEN the owner does not have an avatar_url
THEN the header renders the owner's initials as a fallback avatar.
AND no broken image is shown.
