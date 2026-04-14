# EP-02 Backend Tasks — Capture Form, Draft Auto-Save & Templates

Branch: `feature/ep-02-backend`
Refs: EP-02
Depends on: EP-01 backend (work_items table, WorkItem entity, WorkItemService)

---

## API Contract (Frontend Dependency)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PATCH | `/api/v1/work-items/{id}/draft` | JWT | Auto-save draft_data on committed item (Draft state only) |
| GET | `/api/v1/work-item-drafts` | JWT | Get current pre-creation draft for user+workspace |
| POST | `/api/v1/work-item-drafts` | JWT | Upsert pre-creation draft (versioned) |
| DELETE | `/api/v1/work-item-drafts/{id}` | JWT | Discard draft |
| GET | `/api/v1/templates` | JWT | List templates for workspace+type (`?type=bug&workspace_id=...`) |
| POST | `/api/v1/templates` | JWT (admin) | Create workspace template |
| PATCH | `/api/v1/templates/{id}` | JWT (admin) | Update workspace template |
| DELETE | `/api/v1/templates/{id}` | JWT (admin) | Delete workspace template |

**PATCH /work-items/{id}/draft** request:
```json
{ "draft_data": { "description": "partial...", "priority": "high" } }
```
Response: `{ "data": { "id": "uuid", "draft_saved_at": "ISO8601" }, "message": "Draft saved" }`

**POST /work-item-drafts** request:
```json
{ "workspace_id": "uuid", "data": { "title": "...", "type": "bug" }, "local_version": 1 }
```
409 conflict response:
```json
{ "error": { "code": "DRAFT_VERSION_CONFLICT", "message": "...", "details": { "server_version": 3, "server_data": {} } } }
```

**GET /templates** response item:
```json
{ "id": "uuid", "type": "bug", "name": "Bug Report", "content": "## Summary\n...", "is_system": false }
```

---

## Phase 1 — Database Migrations

- [ ] Write Alembic migration: add `draft_data JSONB` and `template_id UUID REFERENCES templates(id) ON DELETE SET NULL` columns to `work_items`; add index `idx_work_items_template` on `(template_id)` where not null
- [ ] Write Alembic migration: create `work_item_drafts` table — `id`, `user_id FK`, `workspace_id FK`, `data JSONB NOT NULL DEFAULT '{}'`, `local_version INT NOT NULL DEFAULT 1`, `incomplete BOOLEAN NOT NULL DEFAULT TRUE`, `created_at`, `updated_at`, `expires_at DEFAULT now() + INTERVAL '30 days'`; UNIQUE `(user_id, workspace_id)`; index on `expires_at WHERE expires_at < now()`
- [ ] Write Alembic migration: create `templates` table — all columns per design.md; CHECK constraints for `type` (8 valid values), `content` length (≤50000), `is_system + workspace_id` mutual exclusion; unique index `(workspace_id, type) WHERE workspace_id IS NOT NULL`; unique index `(type) WHERE is_system = TRUE`
- [ ] Verify migrations apply and roll back cleanly on fresh DB

---

## Phase 2 — Domain Layer

### WorkItemDraft Entity

- [ ] [RED] Write unit tests for `WorkItemDraft` dataclass: construction with valid fields, `expires_at` defaults to 30 days from now, field types match schema
- [ ] [GREEN] Implement `domain/models/work_item_draft.py` — `WorkItemDraft` dataclass: `id`, `user_id`, `workspace_id`, `data: dict`, `local_version: int`, `incomplete: bool`, `created_at`, `updated_at`, `expires_at`

### Template Entity

- [ ] [RED] Write unit tests for `Template` dataclass: `is_system=True` with `workspace_id` set raises invariant error, `content` longer than 50000 chars raises, `type` must be valid `WorkItemType`
- [ ] [GREEN] Implement `domain/models/template.py` — `Template` dataclass: `id`, `workspace_id: UUID | None`, `type: WorkItemType`, `name`, `content`, `is_system`, `created_by: UUID | None`, `created_at`, `updated_at`

### WorkItem Entity Extensions

- [ ] [RED] Write tests for `WorkItem` extensions: `draft_data` is cleared when state advances out of `DRAFT`, `template_id` remains unchanged on subsequent updates (immutable after set)
- [ ] [GREEN] Extend `domain/models/work_item.py` with `draft_data: dict | None` and `template_id: UUID | None` fields

---

## Phase 3 — Repository Layer

### WorkItemDraftRepository

- [ ] Implement `domain/repositories/work_item_draft_repository.py` — `IWorkItemDraftRepository` ABC: `upsert(draft, expected_version) -> WorkItemDraft | DraftConflict`, `get_by_user_workspace(user_id, workspace_id) -> WorkItemDraft | None`, `delete(draft_id, user_id) -> None`, `get_expired() -> list[WorkItemDraft]`
- [ ] [RED] Write integration tests against real test DB:
  - Upsert with matching version creates/updates record and increments `local_version`
  - Upsert with lower client version (stale) returns `DraftConflict` with server data
  - UNIQUE constraint enforced: second upsert for same user+workspace updates existing row
  - `get_by_user_workspace` returns None when no draft exists
  - `delete` by non-owner raises or returns not-found
- [ ] [GREEN] Implement `infrastructure/persistence/work_item_draft_repository.py`

### TemplateRepository

- [ ] Implement `domain/repositories/template_repository.py` — `ITemplateRepository` ABC: `get_by_workspace_and_type(workspace_id, type) -> Template | None`, `get_system_default(type) -> Template | None`, `create(template) -> Template`, `update(template_id, data) -> Template`, `delete(template_id) -> None`, `list_for_workspace(workspace_id) -> list[Template]`
- [ ] [RED] Write integration tests:
  - `get_by_workspace_and_type` returns workspace template when it exists
  - Returns None when no workspace template (system fallback is service responsibility, not repo)
  - Duplicate `(workspace_id, type)` raises constraint error
  - System template cannot have `workspace_id` set (DB constraint enforced)
- [ ] [GREEN] Implement `infrastructure/persistence/template_repository.py`

### WorkItemRepository Extensions

- [ ] [RED] Write integration tests for extended `WorkItemRepository`: save/load `draft_data` JSONB preserves nested structure, save/load `template_id` FK round-trip
- [ ] [GREEN] Extend `infrastructure/persistence/work_item_repository.py` to handle new columns

---

## Phase 4 — Application Services

### DraftService

- [ ] [RED] Write unit tests using fake repository:
  - `upsert_pre_creation_draft`: valid version → returns updated `WorkItemDraft` with incremented `local_version`
  - `upsert_pre_creation_draft`: client version behind server → returns `DraftConflict` with `server_version` and `server_data`
  - `save_committed_draft`: item in `DRAFT` state → writes to `work_items.draft_data` without updating `updated_at`
  - `save_committed_draft`: item in non-DRAFT state → raises `InvalidStateError`
  - `discard_pre_creation_draft`: owned by user → deletes, not owned → raises not-found/forbidden
- [ ] [GREEN] Implement `application/services/draft_service.py`
- [ ] [REFACTOR] `save_committed_draft` must NOT update `work_items.updated_at` — audit trail must not include auto-save events

### Acceptance Criteria — DraftService

See also: specs/capture/spec.md (US-021)

WHEN `upsert_pre_creation_draft(user_id, workspace_id, data, local_version=1)` is called with no existing draft
THEN a new draft is created with `local_version = 1`
AND `incomplete = True` if data would fail full creation validation

WHEN `upsert_pre_creation_draft()` is called with `local_version = 2` but server has `local_version = 3`
THEN it returns a `DraftConflict` object with `server_version = 3` and `server_data` (current DB content)
AND the DB draft is NOT overwritten

WHEN `save_committed_draft(item_id, draft_data={...})` is called on a `DRAFT`-state work item
THEN `work_items.draft_data` is updated in the DB
AND `work_items.updated_at` is NOT changed (verify by reading `updated_at` before and after)

WHEN `save_committed_draft(item_id, draft_data={...})` is called on an `IN_REVIEW` work item
THEN it raises `InvalidStateError`

WHEN `discard_pre_creation_draft(draft_id, user_id)` is called by a user who does not own the draft
THEN it raises `ForbiddenError` (not silently succeeds)

### TemplateService

- [ ] [RED] Write unit tests using fake repository + fake Redis:
  - `get_template_for_type`: workspace template exists → returns it; workspace template absent → returns system default; neither → returns None
  - `get_template_for_type`: cache hit → no DB call (verify with fake cache)
  - `create_template`: non-admin actor → raises `ForbiddenError`; duplicate type → raises `DuplicateTemplateError`; content > 50000 chars → raises validation error
  - `update_template`: system template → raises `ForbiddenError`; valid update → invalidates Redis cache
  - `delete_template`: system template → raises `ForbiddenError`; valid delete → invalidates cache
- [ ] [GREEN] Implement `application/services/template_service.py`
- [ ] [REFACTOR] Redis cache key convention: `template:{workspace_id}:{type}` and `template:system:{type}`, TTL 5 minutes; invalidate on write

### Acceptance Criteria — TemplateService

See also: specs/templates/spec.md (US-022)

WHEN `get_template_for_type(workspace_id, type="bug")` is called and workspace template exists
THEN the workspace-specific template is returned (not the system default)

WHEN `get_template_for_type(workspace_id, type="bug")` is called and NO workspace template exists but a system default does
THEN the system default template is returned

WHEN `get_template_for_type(workspace_id, type="bug")` is called again within the 5-min TTL
THEN the result is served from Redis cache (fake repo `get_by_workspace_and_type` is NOT called)

WHEN `create_template(workspace_id, type, content, actor_id=non_admin_user_id)` is called
THEN it raises `ForbiddenError` (admin-only operation)

WHEN `create_template(workspace_id, type="bug", ...)` is called and a workspace template for `bug` already exists
THEN it raises `DuplicateTemplateError`

WHEN `update_template(template_id, content=new_content)` is called on a system template (`is_system=True`)
THEN it raises `ForbiddenError`

WHEN `update_template()` succeeds
THEN Redis cache key `template:{workspace_id}:{type}` is deleted (not just updated)

---

## Phase 5 — Redis Caching

- [ ] Add cache layer in `TemplateService.get_template_for_type()`: Redis GET before DB query; Redis SET after DB hit; return cached result when hit
- [ ] Invalidate cache in `create_template()`, `update_template()`, `delete_template()` after successful DB write
- [ ] [RED] Write tests: cache hit avoids DB call (fake cache returns value → fake repo not called), cache miss falls through to DB and populates cache

---

## Phase 6 — API Controllers

### WorkItemDraftController

- [ ] [RED] Write integration tests for `POST /api/v1/work-item-drafts`:
  - 200 + `{ draft_id, local_version }` on successful upsert
  - 409 + `DRAFT_VERSION_CONFLICT` with `server_version` and `server_data` on version conflict
  - 401 on unauthenticated request
- [ ] [RED] Write integration tests for `GET /api/v1/work-item-drafts`: returns current draft object; returns `null` when no draft exists
- [ ] [RED] Write integration tests for `DELETE /api/v1/work-item-drafts/{id}`: 204 on success, 403 if not owned by requesting user
- [ ] [GREEN] Implement `presentation/controllers/work_item_draft_controller.py`

### WorkItem Draft Route Extension

- [ ] [RED] Write integration tests for `PATCH /api/v1/work-items/{id}/draft`:
  - 200 + `{ id, draft_saved_at }` when item in Draft state
  - 409 `INVALID_STATE` when item not in Draft state
  - 401 unauthenticated
  - 403 non-owner
- [ ] [GREEN] Add `PATCH /work-items/{id}/draft` route to existing work item controller

### TemplateController

- [ ] [RED] Write integration tests for `GET /api/v1/templates`: returns workspace override when it exists, returns system default when no workspace template, returns `null` when neither exists; 401 unauthenticated
- [ ] [RED] Write integration tests for `POST /api/v1/templates`: admin creates → 201; non-admin → 403; duplicate type → 409; content too long → 422
- [ ] [RED] Write integration tests for `PATCH /api/v1/templates/{id}`: admin updates → 200; system template → 403; non-admin → 403
- [ ] [RED] Write integration tests for `DELETE /api/v1/templates/{id}`: admin deletes → 204; system template → 403
- [ ] [GREEN] Implement `presentation/controllers/template_controller.py`

### Acceptance Criteria — Controllers (Phase 6)

See also: specs/capture/spec.md (US-021), specs/templates/spec.md (US-022)

**POST /api/v1/work-item-drafts**
WHEN called with `{ workspace_id, data: {...}, local_version: 1 }` and no existing draft
THEN response is HTTP 200 `{ "data": { "draft_id": "uuid", "local_version": 1 } }`

WHEN called with `local_version: 1` but server has version 3
THEN response is HTTP 409 `{ "error": { "code": "DRAFT_VERSION_CONFLICT", "details": { "server_version": 3, "server_data": {...} } } }`

WHEN called unauthenticated
THEN response is HTTP 401

**GET /api/v1/work-item-drafts**
WHEN a draft exists for the requesting user+workspace
THEN response is HTTP 200 with the full `WorkItemDraft` object

WHEN no draft exists
THEN response is HTTP 200 with `{ "data": null }`

**DELETE /api/v1/work-item-drafts/{id}**
WHEN called by the draft owner
THEN response is HTTP 204 and draft is deleted

WHEN called by a different user
THEN response is HTTP 403

**PATCH /api/v1/work-items/{id}/draft**
WHEN item is in `DRAFT` state and caller is owner
THEN response is HTTP 200 `{ "data": { "id": "uuid", "draft_saved_at": "ISO8601" } }`
AND `work_items.updated_at` is NOT changed

WHEN item is NOT in `DRAFT` state
THEN response is HTTP 409 `{ "error": { "code": "INVALID_STATE" } }`

**GET /api/v1/templates?type=bug**
WHEN workspace template for `bug` exists
THEN response is HTTP 200 with that template as `data`

WHEN no workspace template but system default exists
THEN response is HTTP 200 with the system default template

WHEN neither exists
THEN response is HTTP 200 with `{ "data": null }`

**POST /api/v1/templates**
WHEN admin sends `{ type: "bug", name: "Bug Report", content: "## Summary\n..." }`
THEN response is HTTP 201 with the created template including `id`

WHEN non-admin sends the request
THEN response is HTTP 403

WHEN a workspace template for `bug` already exists
THEN response is HTTP 409 `{ "error": { "code": "DUPLICATE_TEMPLATE" } }`

WHEN `content` exceeds 50,000 characters
THEN response is HTTP 422 `{ "error": { "code": "VALIDATION_ERROR", "details": { "field": "content" } } }`

**PATCH /api/v1/templates/{id} on a system template**
THEN response is HTTP 403

**DELETE /api/v1/templates/{id} on a system template**
THEN response is HTTP 403

### EP-01 Work Item Controller Extension

- [ ] Extend `POST /api/v1/work-items` to accept `template_id` (optional), validate it belongs to requesting workspace or is system, store on `work_items.template_id`
- [ ] [REFACTOR] Audit all new endpoints: auth check, authz check, input validation at system boundary

---

## Phase 7 — Background Job: Draft Expiry

- [ ] [RED] Write unit test for `expire_drafts` Celery task: selects only drafts where `expires_at < now()`, deletes them, returns count deleted, no-op when no expired drafts exist
- [ ] [GREEN] Implement `infrastructure/jobs/expire_drafts_task.py` — Celery task
- [ ] Register in Celery Beat: daily at 02:00 UTC

---

## Phase 8 — Error Middleware Extensions

- [ ] Add: `InvalidStateError → 409 INVALID_STATE`
- [ ] Add: `DraftConflict → 409 DRAFT_VERSION_CONFLICT` (with `server_version`, `server_data` in details)
- [ ] Add: `DuplicateTemplateError → 409 DUPLICATE_TEMPLATE`
- [ ] Add: `ForbiddenError → 403 FORBIDDEN`

---

## Definition of Done

- [ ] All unit and integration tests pass
- [ ] `mypy --strict` clean
- [ ] `ruff` clean
- [ ] All 9 new endpoints handle happy path and documented error cases
- [ ] Template Redis caching verified: second GET within 60s does not hit DB
- [ ] Draft expiry job runs without error on empty and populated datasets
- [ ] `draft_data` writes do not change `work_items.updated_at` (verified in integration test)
