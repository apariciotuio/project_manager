# EP-02 — Technical Design

## Schema Extensions to EP-01

EP-01's `work_items` table already includes `original_input TEXT`. EP-02 adds two columns and a new table.

### Additions to `work_items`

```sql
ALTER TABLE work_items
    ADD COLUMN draft_data     JSONB,
    ADD COLUMN template_id    UUID REFERENCES templates(id) ON DELETE SET NULL;

CREATE INDEX idx_work_items_template ON work_items(template_id) WHERE template_id IS NOT NULL AND deleted_at IS NULL;
```

`draft_data` is a freeform JSONB blob holding in-progress field values for a committed Draft-state item being edited. It is distinct from `original_input` (which is immutable after creation) and from `description` (the committed field). On transition out of `Draft`, `draft_data` is cleared.

`template_id` is a snapshot reference — it records which template was applied at creation for audit. Updating the template later does not affect this column.

### `work_item_drafts` table (pre-creation drafts)

Holds transient form state before the user confirms creation. Keyed by `(user_id, workspace_id)` — one pre-creation draft per user per workspace at a time.

```sql
CREATE TABLE work_item_drafts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    data            JSONB NOT NULL DEFAULT '{}',
    local_version   INTEGER NOT NULL DEFAULT 1,
    incomplete      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT now() + INTERVAL '30 days',

    CONSTRAINT work_item_drafts_unique_user_workspace UNIQUE (user_id, workspace_id)
);

CREATE INDEX idx_work_item_drafts_expires ON work_item_drafts(expires_at)
    WHERE expires_at < now();
```

### `templates` table

```sql
CREATE TABLE templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    UUID REFERENCES workspaces(id) ON DELETE CASCADE,  -- NULL = system default
    type            VARCHAR(50) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    schema          JSONB NOT NULL,          -- JSON-schema typed template document (Layer 3) — see specs/templates/spec.md
    version         INTEGER NOT NULL DEFAULT 1,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    created_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT templates_type_valid CHECK (type IN (
        'idea','bug','mejora','tarea','iniciativa','spike','cambio','requisito',
        'milestone','story'
    )),
    CONSTRAINT templates_system_no_workspace CHECK (
        NOT (is_system = TRUE AND workspace_id IS NOT NULL)
    )
);

-- One workspace-level template per type per workspace (can override system default)
CREATE UNIQUE INDEX idx_templates_workspace_type
    ON templates(workspace_id, type)
    WHERE workspace_id IS NOT NULL;

-- One system template per type
CREATE UNIQUE INDEX idx_templates_system_type
    ON templates(type)
    WHERE is_system = TRUE;

CREATE INDEX idx_templates_workspace ON templates(workspace_id) WHERE workspace_id IS NOT NULL;
```

Template lookup precedence: workspace-specific first, system default fallback.

---

## Auto-Save Strategy

### Debounce interval: 3 seconds

3s is the standard for "user has paused typing" UX. 1s creates too many requests on slow connections; 5s risks data loss on abrupt navigation.

### Pre-creation draft flow

```
User types → 3s debounce → POST /api/v1/work-item-drafts
  { workspace_id, data: { title, type, description, ... }, local_version }

Server:
  - UPSERT on (user_id, workspace_id)
  - If server.local_version > client.local_version → return 409 { server_version, server_data }
  - Else → update, increment local_version, reset expires_at, return 200 { draft_id, local_version }
```

### Post-creation draft flow (committed Draft-state item)

```
User edits committed Draft item → 3s debounce → PATCH /api/v1/work-items/{id}/draft
  { draft_data: { ...partial fields... } }

Server:
  - Validates item is in Draft state (else 409 INVALID_STATE)
  - Writes to work_items.draft_data
  - Does NOT update work_items.updated_at (avoids polluting audit trail with keystrokes)
  - Returns 200
```

### Multi-tab conflict resolution

Last-write-wins with optimistic versioning. The `local_version` integer is a monotonic counter held in localStorage per draft_id. On 409, the frontend shows a non-blocking banner: "Another tab has newer changes. [Keep mine] [Load latest]". This is the correct tradeoff: drafts are ephemeral; the cost of losing a few keystrokes is lower than the complexity of merge resolution.

Decision: do NOT implement CRDT or OT for drafts. This is pre-creation transient state, not a collaborative document. Over-engineering this is the wrong call.

---

## Template Storage Model

Templates are JSON-schema typed documents (see `specs/templates/spec.md`). The structure has three layers:

- **Layer 1** — eight immutable universal sections (code-owned).
- **Layer 2** — immutable field-type catalogue (`text`, `string`, `enum`, `multi_enum`, `date`, `date_range`, `duration`, `reference`, `reference_list`, `user_reference`, `user_list`, `attachment_list`) with `required`, `prefill`, `help_text`, `validation`.
- **Layer 3** — editable per-type concrete templates (the `schema` JSONB column).

All template mutations are validated against the JSON schema before persistence. Structural changes that would remove a universal section or introduce an unknown field type are rejected HTTP 422.

Template lookup is a two-step query:

```sql
-- Step 1: workspace override
SELECT * FROM templates WHERE workspace_id = :workspace_id AND type = :type LIMIT 1;

-- Step 2: system default fallback (if step 1 returns nothing)
SELECT * FROM templates WHERE is_system = TRUE AND type = :type LIMIT 1;
```

This is two cheap indexed lookups, not a UNION. The service layer decides which to use.

Templates are cached in Redis with key `template:{workspace_id}:{type}` and `template:system:{type}`, TTL 5 minutes. Cache invalidated on template write.

---

## API Endpoints

All under `/api/v1/`. Auth: JWT required on all endpoints.

| Method | Path | Description | Notes |
|--------|------|-------------|-------|
| POST | `/work-items` | Create work item (commits, sets original_input) | EP-01 already defined; EP-02 adds template_id application |
| PATCH | `/work-items/{id}/draft` | Auto-save draft_data on committed item | Only valid in Draft state |
| GET | `/work-item-drafts` | Get current pre-creation draft for user+workspace | Returns null if none |
| POST | `/work-item-drafts` | Upsert pre-creation draft | Versioned, idempotent |
| DELETE | `/work-item-drafts/{id}` | Discard draft | User-initiated |
| GET | `/templates` | List templates for workspace+type | Query params: type, include_system |
| POST | `/templates` | Create workspace template | Admin only |
| PATCH | `/templates/{id}` | Update workspace template | Admin only |
| DELETE | `/templates/{id}` | Delete workspace template (system templates: 403) | Admin only |

### POST /work-items (EP-02 additions)

Request additions:
```json
{
  "title": "string (3-255)",
  "type": "bug",
  "description": "string (optional)",
  "template_id": "uuid (optional, client passes if template was applied)"
}
```

Server behavior: if `template_id` is provided, validates it exists and belongs to this workspace (or is system). Stores on the row. `original_input` is set to `title` verbatim (immutable from this point).

### PATCH /work-items/{id}/draft

```json
{
  "draft_data": {
    "description": "partial text...",
    "priority": "high"
  }
}
```

Response: `{ "data": { "id": "uuid", "draft_saved_at": "ISO8601" }, "message": "Draft saved" }`

### POST /work-item-drafts

```json
{
  "workspace_id": "uuid",
  "data": { "title": "...", "type": "bug", "description": "..." },
  "local_version": 1
}
```

409 response when version conflict:
```json
{
  "error": {
    "code": "DRAFT_VERSION_CONFLICT",
    "message": "Server has a newer version of this draft",
    "details": { "server_version": 3, "server_data": { ... } }
  }
}
```

---

## Frontend Component Design

### CaptureForm (new component)

```
CaptureForm
  TypeSelector          — dropdown of 8 types, triggers template fetch on change
  TitleInput            — controlled, fires debounced auto-save
  DescriptionEditor     — Markdown editor, pre-populated from template
  DraftResumeBanner     — shown on mount if draft exists, "Resume" / "Discard" actions
  StalenessWarning      — shown on 409 draft conflict, inline banner
  SubmitButton          — disabled until title >= 3 chars and type selected
  CancelButton          — discards draft (with confirmation if draft has content)
```

State management: React local state + `useAutoSave` hook (encapsulates debounce + version tracking). No global store needed for creation flow — it is ephemeral per-session.

`useAutoSave` hook contract:
```typescript
function useAutoSave(params: {
  workspaceId: string
  draftId: string | null
  onDraftSaved: (draftId: string, version: number) => void
  onConflict: (serverData: DraftData, serverVersion: number) => void
}): {
  save: (data: DraftData) => void   // debounced 3s
  isSaving: boolean
  lastSavedAt: Date | null
}
```

### WorkItemHeader (display component, existing EP-01 skeleton — EP-02 extends)

```
WorkItemHeader
  TypeBadge             — colored chip per type
  TitleText             — editable inline (owner only, Draft state)
  StatechChip           — primary state + derived_state indicator
  OwnerWidget           — avatar + name, suspended warning if applicable
  CompletenessBar       — 0-100 filled bar, percentage label
  NextStepHint          — conditional, shown when completeness < 30
```

`WorkItemHeader` receives the full work item response object and is purely presentational. No data fetching inside the component. Completeness score and derived_state come pre-computed from the API.

### Template application flow

```
User selects type
  → GET /api/v1/templates?type={type}&workspace_id={id}
  → if template exists: populate DescriptionEditor, store template_id in form state
  → if user has edited description already: show confirmation modal before overwrite
  → on type change: repeat with new type, show confirmation if description non-empty
```

Template fetch is triggered on type change with a 200ms delay (avoids fetching on rapid type cycling). Cached in React Query with staleTime: 5 minutes.

---

## Domain Layer Changes

### WorkItemDraft entity (new, domain/models/work_item_draft.py)

```python
@dataclass
class WorkItemDraft:
    id: UUID
    user_id: UUID
    workspace_id: UUID
    data: dict                  # freeform, no validation
    local_version: int
    incomplete: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
```

### Template entity (new, domain/models/template.py)

```python
@dataclass
class Template:
    id: UUID
    workspace_id: UUID | None   # None = system default
    type: WorkItemType
    name: str
    content: str                # Markdown
    is_system: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
```

### WorkItem entity (extension)

Add to the existing `WorkItem` dataclass:
```python
    draft_data: dict | None     # transient edit buffer, cleared on state advance
    template_id: UUID | None    # audit reference, immutable after set
```

`original_input` already exists in EP-01. No change needed.

---

## Application Service: DraftService (new)

```python
# application/services/draft_service.py

async def upsert_pre_creation_draft(
    user_id: UUID, workspace_id: UUID, data: dict, local_version: int
) -> WorkItemDraft | DraftConflict

async def get_pre_creation_draft(user_id: UUID, workspace_id: UUID) -> WorkItemDraft | None

async def discard_pre_creation_draft(user_id: UUID, draft_id: UUID) -> None

async def save_committed_draft(
    item_id: UUID, actor_id: UUID, draft_data: dict
) -> None  # raises InvalidStateError if not Draft state
```

## Application Service: TemplateService (new)

```python
# application/services/template_service.py

async def get_template_for_type(type: WorkItemType, workspace_id: UUID) -> Template | None

async def create_template(command: CreateTemplateCommand, actor_id: UUID) -> Template

async def update_template(template_id: UUID, command: UpdateTemplateCommand, actor_id: UUID) -> Template

async def delete_template(template_id: UUID, actor_id: UUID) -> None
```

---

## Alternatives Considered

### IndexedDB-only drafts (no server backup)

Rejected. IndexedDB is cleared on browser storage purge, private browsing, and some mobile browsers. Server backup is non-negotiable for data that users expect to survive.

### CRDT for multi-tab conflict resolution

Rejected. Drafts are pre-creation throwaway state. The complexity of CRDT (Yjs or Automerge) is not justified. Last-write-wins with a version conflict warning is sufficient and honest with the user.

### Template as JSON schema (structured sections)

Considered. A JSON schema would allow field-level pre-population (not just description). Rejected: the 8 item types all share the same field set, so "template = structured scaffold for description field as Markdown" is sufficient. JSON schema templates become relevant only if we introduce type-specific custom fields (deferred). ⚠️ originally MVP-scoped — see decisions_pending.md

### Separate `drafts` microservice

Not even worth rejecting. It's a few DB rows and a debounce hook. Microservices are not architecture — they're a cost center unless justified by independent scaling or deployment requirements. Neither applies here.
