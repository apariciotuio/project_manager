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

- [x] Write Alembic migration: add `draft_data JSONB` and `template_id UUID REFERENCES templates(id) ON DELETE SET NULL` columns to `work_items`; add index `idx_work_items_template` on `(template_id)` where not null — 2026-04-15, 0011 + 0013 migrations created
- [x] Write Alembic migration: create `work_item_drafts` table — `id`, `user_id FK`, `workspace_id FK`, `data JSONB NOT NULL DEFAULT '{}'`, `local_version INT NOT NULL DEFAULT 1`, `incomplete BOOLEAN NOT NULL DEFAULT TRUE`, `created_at`, `updated_at`, `expires_at DEFAULT now() + INTERVAL '30 days'`; UNIQUE `(user_id, workspace_id)`; index on `expires_at` — 2026-04-15, 0012 migration created
- [x] Write Alembic migration: create `templates` table — all columns per design.md; CHECK constraints for `type` (8 valid values), `content` length (≤50000), `is_system + workspace_id` mutual exclusion; unique index `(workspace_id, type) WHERE workspace_id IS NOT NULL`; unique index `(type) WHERE is_system = TRUE` — 2026-04-15, 0013 migration created
- [x] Verify migrations apply and roll back cleanly on fresh DB — 2026-04-15, 9 migration tests pass

---

## Phase 2 — Domain Layer

### WorkItemDraft Entity

- [x] [RED] Write unit tests for `WorkItemDraft` dataclass: construction with valid fields, `expires_at` defaults to 30 days from now, field types match schema — 2026-04-15, 6 tests
- [x] [GREEN] Implement `domain/models/work_item_draft.py` — `WorkItemDraft` dataclass: `id`, `user_id`, `workspace_id`, `data: dict`, `local_version: int`, `incomplete: bool`, `created_at`, `updated_at`, `expires_at` — 2026-04-15, all tests pass

### Template Entity

- [x] [RED] Write unit tests for `Template` dataclass: `is_system=True` with `workspace_id` set raises invariant error, `content` longer than 50000 chars raises, `type` must be valid `WorkItemType` — 2026-04-15, 6 tests
- [x] [GREEN] Implement `domain/models/template.py` — `Template` dataclass: `id`, `workspace_id: UUID | None`, `type: WorkItemType`, `name`, `content`, `is_system`, `created_by: UUID | None`, `created_at`, `updated_at` — 2026-04-15, all tests pass

### WorkItem Entity Extensions

- [x] [RED] Write tests for `WorkItem` extensions: `draft_data` is cleared when state advances out of `DRAFT`, `template_id` remains unchanged on subsequent updates (immutable after set) — 2026-04-15, 4 tests
- [x] [GREEN] Extend `domain/models/work_item.py` with `draft_data: dict | None` and `template_id: UUID | None` fields — 2026-04-15, all 206 domain tests pass

---

## Phase 3 — Repository Layer

### WorkItemDraftRepository

- [x] Implement `domain/repositories/work_item_draft_repository.py` — `IWorkItemDraftRepository` ABC — 2026-04-15
- [x] [RED] Write integration tests against real test DB — 2026-04-15, 9 tests
- [x] [GREEN] Implement `infrastructure/persistence/work_item_draft_repository_impl.py` — 2026-04-15, all pass

### TemplateRepository

- [x] Implement `domain/repositories/template_repository.py` — `ITemplateRepository` ABC — 2026-04-15
- [x] [RED] Write integration tests — 2026-04-15, 10 tests
- [x] [GREEN] Implement `infrastructure/persistence/template_repository_impl.py` — 2026-04-15, all pass

### WorkItemRepository Extensions

- [x] [RED] Write integration tests for extended `WorkItemRepository` — 2026-04-15, 3 tests
- [x] [GREEN] Extend ORM, mapper, and `_build_values` to handle draft_data/template_id — 2026-04-15, all pass

---

## Phase 4 — Application Services

### DraftService

- [x] [RED] Write unit tests using fake repository — 2026-04-15, 10 tests
- [x] [GREEN] Implement `application/services/draft_service.py` — 2026-04-15, all pass
- [x] [REFACTOR] `save_committed_draft` restores `updated_at` before saving — 2026-04-15

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

- [x] [RED] Write unit tests using fake repository + fake cache — 2026-04-15, 10 tests
- [x] [GREEN] Implement `application/services/template_service.py` — 2026-04-15, all pass
- [x] [REFACTOR] Redis cache key convention implemented, TTL 5min, invalidate on write — 2026-04-15

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

- [x] Add cache layer in `TemplateService.get_template_for_type()` — 2026-04-15, implemented in Phase 4
- [x] Invalidate cache in `create_template()`, `update_template()`, `delete_template()` — 2026-04-15
- [x] [RED] Tests: cache hit avoids DB call (test_cache_hit_avoids_db_call passes) — 2026-04-15

---

## Phase 6 — API Controllers

### WorkItemDraftController

- [x] [RED] Integration tests for `POST /api/v1/work-item-drafts` — 200 upsert / 409 DRAFT_VERSION_CONFLICT / 401 — 2026-04-16, see `tests/integration/test_work_item_draft_controller.py`
- [x] [RED] Integration tests for `GET /api/v1/work-item-drafts` — returns object / null — 2026-04-16
- [x] [RED] Integration tests for `DELETE /api/v1/work-item-drafts/{id}` — 204 / 403 / 404 — 2026-04-16
- [x] [GREEN] `presentation/controllers/work_item_draft_controller.py` — 2026-04-16; DELETE exceptions bubble to global middleware (no inline HTTPException)

### WorkItem Draft Route Extension

- [x] [RED] Integration tests for `PATCH /api/v1/work-items/{id}/draft` — 200 / 409 INVALID_STATE / 401 / 403 — 2026-04-16, see `tests/integration/test_work_item_controller.py`
- [x] [GREEN] `PATCH /work-items/{id}/draft` route added — 2026-04-16; uses `Depends(get_draft_service)`, `WorkItemInvalidStateError` bubbles to middleware

### TemplateController

- [x] [RED] Integration tests for `GET /api/v1/templates` — workspace override / system default / null / 401 — 2026-04-16, see `tests/integration/test_template_controller.py`
- [x] [RED] Integration tests for `POST /api/v1/templates` — 201 / 403 non-admin / 409 duplicate / 422 too long — 2026-04-16
- [x] [RED] Integration tests for `PATCH /api/v1/templates/{id}` — 200 admin / 403 system / 403 non-admin — 2026-04-16
- [x] [RED] Integration tests for `DELETE /api/v1/templates/{id}` — 204 admin / 403 system — 2026-04-16
- [x] [GREEN] `presentation/controllers/template_controller.py` — 2026-04-16; role resolved via `Depends(get_membership_repo_scoped)`, no private `_repo` access
- [x] [REFACTOR] Extracted `get_cache_adapter` dependency so tests override with `FakeCache` (no Redis required) — 2026-04-16

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

- [x] `POST /api/v1/work-items` accepts optional `template_id`; stored on `work_items.template_id` via `CreateWorkItemCommand` — 2026-04-16
- [x] [REFACTOR] All EP-02 endpoints audited — auth via `get_current_user`, authz via role check or state check, input validation via Pydantic schemas — 2026-04-16

**Status: COMPLETED** (2026-04-16)

---

## Phase 7 — Background Job: Draft Expiry

- [x] [RED] Write unit test for `expire_drafts` Celery task: selects only drafts where `expires_at < now()`, deletes them, returns count deleted, no-op when no expired drafts exist — 4 unit tests in `tests/unit/infrastructure/jobs/test_expire_drafts.py`; also added `DraftService.expire_pre_creation_drafts` TDD with same unit tests
- [x] [GREEN] Implement `infrastructure/jobs/expire_drafts_task.py` — Celery task `expire_work_item_drafts`; `DraftService.expire_pre_creation_drafts` added; integration test in `tests/integration/test_expire_drafts_job.py`
- [x] Register in Celery Beat: daily at 02:00 UTC — added `expire-work-item-drafts-daily` entry in `app/config/celery_app.py`

**Status: COMPLETED** (2026-04-16)

---

## Phase 8 — Error Middleware Extensions

- [x] `WorkItemInvalidStateError → 409 INVALID_STATE` (with `expected_state`, `actual_state`) — registered in `error_middleware.py`
- [x] `DraftConflict → 409 DRAFT_VERSION_CONFLICT` — handled inline in `POST /work-item-drafts` (DraftConflict is a return value, not an exception, by design)
- [x] `DuplicateTemplateError → 409 DUPLICATE_TEMPLATE`
- [x] `TemplateForbiddenError → 403 FORBIDDEN`
- [x] `TemplateNotFoundError → 404 TEMPLATE_NOT_FOUND`
- [x] `DraftForbiddenError → 403 FORBIDDEN` — 2026-04-16
- [x] `WorkItemDraftNotFoundError → 404 DRAFT_NOT_FOUND` — 2026-04-16

**Status: COMPLETED** (2026-04-16)

---

## Definition of Done

- [x] All unit and integration tests pass — 2026-04-16, 557 passed
- [ ] `mypy --strict` clean — 20 pre-existing errors in untouched files (auth.py, session_repository, celery_app); no new errors from EP-02 Phase 6/7/8 code
- [x] `ruff` clean on EP-02 files — 2026-04-16
- [x] All 9 new endpoints handle happy path and documented error cases — 2026-04-16
- [x] Template Redis caching verified: cache hit avoids DB call — 2026-04-15 unit test; test fixtures use `FakeCache` in-memory to skip Redis dependency
- [x] Draft expiry job runs without error on empty and populated datasets — 2026-04-16, 3 integration tests
- [x] `draft_data` writes do not change `work_items.updated_at` — verified in `DraftService.save_committed_draft` REFACTOR phase
