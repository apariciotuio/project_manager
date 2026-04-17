# EP-04 Backend Tasks — Structured Specification & Quality Engine

Branch: `feature/ep-04-backend`
Refs: EP-04
Depends on: EP-01 backend (work_items, WorkItem entity), EP-03 backend (LLM adapter, PromptRegistry)

---

## API Contract (Frontend Dependency)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/work-items/{id}/specification` | JWT | All sections for a work item |
| POST | `/api/v1/work-items/{id}/specification/generate` | JWT | Trigger LLM generation |
| PATCH | `/api/v1/work-items/{id}/sections/{section_id}` | JWT | Update single section |
| PATCH | `/api/v1/work-items/{id}/sections` | JWT | Bulk update sections (atomic) |
| GET | `/api/v1/work-items/{id}/sections/{section_id}/versions` | JWT | Section version history |
| GET | `/api/v1/work-items/{id}/completeness` | JWT | Weighted score + dimension breakdown |
| GET | `/api/v1/work-items/{id}/gaps` | JWT | Gap list with severity |
| GET | `/api/v1/work-items/{id}/next-step` | JWT | Next step + suggested validators |

**GET /specification response:**
```json
{
  "data": {
    "work_item_id": "uuid",
    "sections": [
      {
        "id": "uuid",
        "section_type": "summary",
        "content": "...",
        "display_order": 1,
        "is_required": true,
        "generation_source": "manual",
        "version": 3,
        "updated_at": "ISO8601",
        "updated_by": "uuid"
      }
    ]
  }
}
```

**GET /completeness response:**
```json
{
  "data": {
    "score": 68,
    "level": "medium",
    "dimensions": [{ "name": "acceptance_criteria", "weight": 0.22, "filled": false, "score": 0.0, "contribution": 0.0 }],
    "computed_at": "ISO8601",
    "cached": true
  }
}
```

**GET /gaps response:**
```json
{ "data": [{ "dimension": "acceptance_criteria", "message": "...", "severity": "blocking" }] }
```

**GET /next-step response:**
```json
{
  "data": {
    "next_step": "define_acceptance_criteria",
    "message": "Add at least 2 acceptance criteria to proceed to review.",
    "blocking": true,
    "gaps_referenced": ["acceptance_criteria"],
    "suggested_validators": [{ "role": "product_owner", "reason": "...", "configured": true }]
  }
}
```

---

## Phase 1 — Database Migrations

- [x] `0017_create_work_item_sections.py` — UNIQUE(work_item_id, section_type), idx_work_item_sections_work_item_id, idx_wis_completeness composite (2026-04-16)
- [x] `0018_create_work_item_section_versions.py` — append-only, FK with ON DELETE CASCADE, idx by section_id + work_item_id (2026-04-16)
- [x] `0019_create_work_item_validators.py` — UNIQUE(work_item_id, role), CHECK on status, indexes on (work_item_id, status) + partial on user_id WHERE status='pending' (2026-04-16)
- [x] `0020_create_work_item_versions.py` — UNIQUE(work_item_id, version_number), idx_wiv_work_item_created DESC (2026-04-16)
- [x] `0021_add_section_id_to_assistant_suggestions.py` — FK added now that work_item_sections exists; orphaned rows nulled before constraint applied (2026-04-16)
- [x] All migrations apply cleanly on fresh DB — verified via full regression (934 passed + 1 skip)

**Status: COMPLETED** (2026-04-16)

> Note: workspace_id + RLS not applied to these 3 new tables per the same deferred follow-up as EP-03 Phase 8 (see `tasks/EP-03/phase_8_security_findings.md` and `decisions.log.md` 2026-04-16). A single future migration will close the RLS gap across EP-03 + EP-04 tables.

---

## Phase 2 — Domain Models

### Section Catalog

- [x] `domain/models/section_type.py` — `SectionType` + `GenerationSource` StrEnums (2026-04-16)
- [x] Unit tests for `SECTION_CATALOG` invariants — all 8 WorkItemTypes covered, ≥1 required section per type, no duplicate section_types, unique display_order per type (2026-04-16 — 33 parametrised tests)
- [x] `domain/models/section_catalog.py` — `SectionConfig` frozen dataclass + `SECTION_CATALOG` dict for all 8 WorkItemType values (2026-04-16)

### Section Entity

- [x] Unit tests: empty content on required section raises `RequiredSectionEmptyError`; empty on optional allowed; `version` increments on `update_content()`; `generation_source` set correctly (2026-04-16 — 5 tests)
- [x] `domain/models/section.py` — `Section` dataclass + `RequiredSectionEmptyError` + `create`/`update_content` (2026-04-16)

### Section / Validator / Work Item Version entities

- [x] `domain/models/section_version.py` — frozen dataclass (append-only VO) (2026-04-16)
- [x] `domain/models/validator.py` — `Validator` entity + `ValidatorStatus` enum; `respond()` sets responded_at; cannot transition back to pending; cannot respond twice (2026-04-16 — 4 tests)
- [x] `domain/models/work_item_version.py` — frozen dataclass; append-only VO (2026-04-16)

### DimensionResult

- [x] `domain/quality/dimension_result.py` — `DimensionResult` + `CompletenessResult` frozen dataclasses (2026-04-16)

**Status: COMPLETED** (2026-04-16) — 42 unit tests, ruff clean, mypy --strict zero errors. Full regression: 934 passed + 1 skipped.

### Repository Interfaces

- [ ] Refactor: all repository methods must accept `workspace_id` as a required parameter — `get(section_id, workspace_id)`, `get_by_work_item(work_item_id, workspace_id)`, etc. Queries must include `WHERE workspace_id = :workspace_id`. Return `None` (not 403) on workspace mismatch to avoid existence disclosure (CRIT-2).
- [ ] Implement `domain/repositories/section_repository.py` — `ISectionRepository` ABC: `get_by_work_item(work_item_id, workspace_id) -> list[Section]`, `get(section_id, workspace_id) -> Section | None`, `save(section) -> Section`, `bulk_save(sections: list[Section]) -> list[Section]`
- [ ] Implement `domain/repositories/section_version_repository.py` — `ISectionVersionRepository` ABC: `append(section, actor_id) -> None`, `get_history(section_id) -> list[SectionVersion]`
- [ ] Implement `domain/repositories/validator_repository.py` — `IValidatorRepository` ABC: `get_by_work_item(work_item_id) -> list[Validator]`, `assign(validator) -> Validator`, `update_status(validator_id, status) -> Validator`
- [ ] Implement `domain/repositories/work_item_version_repository.py` — `IWorkItemVersionRepository` ABC: `append(work_item_id, snapshot, created_by) -> None`, `get_latest(work_item_id) -> WorkItemVersion | None`

---

## Phase 3 — Repository Implementations

- [x] ORM: `WorkItemSectionORM`, `WorkItemSectionVersionORM`, `WorkItemValidatorORM`, `WorkItemVersionORM` in `app/infrastructure/persistence/models/orm.py` (2026-04-16)
- [x] Mappers: `section_mapper.py` covers all 4 domain ↔ ORM conversions (2026-04-16)
- [x] Repository interfaces: `ISectionRepository`, `ISectionVersionRepository`, `IValidatorRepository`, `IWorkItemVersionRepository` in `app/domain/repositories/` (2026-04-16)
- [x] Implementations grouped in `infrastructure/persistence/section_repository_impl.py` (SectionRepositoryImpl + SectionVersionRepositoryImpl + ValidatorRepositoryImpl + WorkItemVersionRepositoryImpl) (2026-04-16)
- [x] Integration tests: 6 tests in `tests/integration/infrastructure/test_section_repository.py` — bulk_insert + ordering, save upsert, section version history descending, validator assign+respond, UNIQUE(work_item_id, role) enforcement, WorkItemVersion auto-increment (2026-04-16)
- [x] `WorkItemVersionRepositoryImpl.append` uses SELECT-MAX-then-INSERT under the UNIQUE(work_item_id, version_number) constraint so concurrent writers surface `IntegrityError` for the caller (typically EP-07 VersioningService) to translate into `VersionConflictError`

**Status: COMPLETED** (2026-04-16) — 940 passed, 1 skipped. ORM-only change (no new migration); ruff clean on new files.

> Note: `SectionRepositoryImpl.save` does NOT automatically append to `work_item_section_versions`. That responsibility belongs to the calling service (Phase 7 SectionService). The repos are thin CRUD; business rules live in the application layer.

---

## Phases 4 + 5 + partial 7 + partial 8 — quality engine + controllers

**Status: BASE IMPLEMENTATION LANDED** (2026-04-16) — 14 new unit tests on the quality engine; full regression 954 passed + 1 skip; ruff + mypy --strict clean on new files.

**EP-04 Phase 4+5+spec-gen callback update** (2026-04-17):
- 44 triangulated unit tests for all 9 dimension checkers (`tests/unit/domain/ep04/test_dimension_checkers.py`)
- 10 unit tests for ScoreCalculator (band assignment, renormalization, ZeroDivisionError guard)
- 8 unit tests for CompletenessService (cache hit/miss/invalidate) + GapService (blocking/warning/empty)
- 2 unit tests for SectionService cache invalidation on update
- `SectionService.update_section` now accepts optional `ICache` dep and calls `cache.delete(completeness:{work_item_id})` post-save
- `wm_spec_gen_agent` callback handler implemented in `dundun_callback_controller.py`: upserts sections by section_type, writes SectionVersion rows, invalidates completeness cache (best-effort)
- 7 integration tests for spec-gen callback (`tests/integration/test_spec_gen_callback.py`)
- Full regression: 1174 passed, 1 skipped

What shipped:
- `domain/quality/dimension_checkers.py` — 9 pure-function checkers (problem_clarity, objective, scope, acceptance_criteria, dependencies, risks, breakdown, ownership, validations) + `DIMENSION_WEIGHTS` table + `check_all()` orchestrator
- `domain/quality/score_calculator.py` — weight renormalisation, 0-100 score, level band mapping, ALG-4 guard against ZeroDivisionError when every dimension is marked inapplicable
- `application/services/completeness_service.py` — `CompletenessService` orchestrating repos + checkers + 60s Redis cache; `GapService` turning the result into a blocking/warning list
- `application/services/section_service.py` — `SectionService.list_for_work_item`, `update_section`, `bootstrap_from_catalog` (append SectionVersion on every update, IDOR + ownership checks inside the service)
- `presentation/controllers/specification_controller.py` — GET `/work-items/{id}/specification`, PATCH `/work-items/{id}/sections/{section_id}`
- `presentation/controllers/completeness_controller.py` — GET `/work-items/{id}/completeness`, GET `/work-items/{id}/gaps`
- `presentation/dependencies.py` — `get_section_service`, `get_completeness_service`, `get_gap_service`
- `main.py` — routers wired under `/api/v1`

What is NOT yet done (deferred within EP-04 — still to be picked up):
- POST `/work-items/{id}/specification/generate` (Dundun `wm_spec_gen_agent` dispatch) — trigger side; callback handler IS now implemented (see 2026-04-17 below)
- PATCH `/work-items/{id}/sections` bulk endpoint
- GET `/work-items/{id}/sections/{section_id}/versions` history endpoint
- `NextStepService` + GET `/work-items/{id}/next-step`
- `ValidatorSuggestionEngine`
- Cache invalidation hooks in `SectionService.update_section`, `WorkItemService.transition_state`, `ValidatorService.update_status` (currently `CompletenessService.invalidate` exists but is not called from other services)
- Full CRUD on validators (assign/revoke/respond endpoints)
- Wiring SectionVersion-per-edit into `VersioningService.create_version` (EP-07's VersioningService is not implemented yet — when it lands, `SectionService.update_section` must call it so the `work_item_versions` snapshot is written)

## Phase 4 — Quality Engine: Dimension Checkers

All dimension checkers are pure functions: `(WorkItem, list[Section], list[Validator]) -> DimensionResult`. No I/O.

- [x] [RED] Write tests for `check_problem_clarity()`: filled when `summary` + `context` combined >= 100 chars; not filled below threshold; returns `applicable=False` for Task, Sub-task, Spike (2026-04-17 — test_dimension_checkers.py)
- [x] [RED] Write tests for `check_objective()`: filled when `objective` section non-empty >= 50 chars; triangulate with 3 inputs: 0 chars, 49 chars, 50 chars (2026-04-17)
- [x] [RED] Write tests for `check_scope()`: applicable for Initiative, Epic, Feature; not applicable for Bug, Task, Spike (2026-04-17)
- [x] [RED] Write tests for `check_acceptance_criteria()`: filled when section has >= 2 bullet points; 1 bullet does not count (2026-04-17)
- [x] [RED] Write tests for `check_dependencies()`: filled when `dependencies` section non-empty OR content = "none" (case-insensitive); empty section is not filled (2026-04-17)
- [x] [RED] Write tests for `check_risks()`: same pattern as `check_dependencies()` (2026-04-17)
- [x] [RED] Write tests for `check_breakdown()`: filled when `breakdown` section has >= 1 line; applicable for Initiative, Epic, Feature (2026-04-17)
- [x] [RED] Write tests for `check_ownership()`: filled when `work_item.owner_id` is set and `owner_suspended_flag = False` (2026-04-17)
- [x] [RED] Write tests for `check_validations()`: filled when at least 1 `Validator` with status `approved` or `pending` (2026-04-17)
- [ ] [RED] Write tests for `check_next_step_clarity()`: deferred (checker not yet implemented)
- [x] [GREEN] Implement all dimension checker functions in `domain/quality/dimension_checkers.py` (2026-04-16)
- [x] [REFACTOR] 100% branch coverage on all dimension checkers; no imports from infrastructure layer (2026-04-17 — 44 tests in test_dimension_checkers.py)

### Acceptance Criteria — Dimension Checkers

See also: specs/quality-engine/spec.md (US-042)

WHEN `check_problem_clarity(work_item, sections, validators)` is called for a `Bug` with `summary` (60 chars) + `actual_behavior` (45 chars) = 105 chars combined
THEN `DimensionResult.filled = True`

WHEN `check_problem_clarity()` is called for a `Bug` with `summary` (30 chars) and no `actual_behavior`
THEN `DimensionResult.filled = False`

WHEN `check_problem_clarity()` is called for a `Task` type
THEN `DimensionResult.applicable = False` (excluded from Task scoring)

WHEN `check_objective()` is called with `objective` section content of 49 chars
THEN `DimensionResult.filled = False`

WHEN `check_objective()` is called with `objective` section content of exactly 50 chars
THEN `DimensionResult.filled = True`

WHEN `check_acceptance_criteria()` is called with `acceptance_criteria` section containing exactly 1 bullet point
THEN `DimensionResult.filled = False` (minimum is 2)

WHEN `check_acceptance_criteria()` is called with `acceptance_criteria` section containing 2 bullet points
THEN `DimensionResult.filled = True`

WHEN `check_dependencies()` is called with `dependencies` section content = "None" (capitalized)
THEN `DimensionResult.filled = True` (case-insensitive "none" check)

WHEN `check_ownership()` is called with `owner_id` set but `owner_suspended_flag = True`
THEN `DimensionResult.filled = False` (suspended owner does not count)

---

## Phase 5 — Completeness Service & Cache

### ScoreCalculator

- [x] [RED] Write unit tests for `ScoreCalculator.compute()`: renormalization, 0/100 boundaries, band assignment, ZeroDivisionError guard (2026-04-17 — test_completeness_service.py: 10 tests)
- [x] [GREEN] Implement `domain/quality/score_calculator.py` (2026-04-16)

### CompletenessCache

- [x] [RED] Write tests for CompletenessService cache hit/miss/invalidate with fake cache (2026-04-17 — test_completeness_service.py: 4 tests)
- [x] [GREEN] Cache is in `CompletenessService` using `ICache` port; key = `completeness:{work_item_id}`, TTL 60s (2026-04-16)

### CompletenessService

- [x] [RED] Write unit tests using fake cache + fake repos: cache hit skips DB, cache miss calls repos, cached flag set (2026-04-17)
- [x] [GREEN] Implement `application/services/completeness_service.py` — `compute(work_item_id) -> CompletenessResult` (2026-04-16)

### GapService

- [x] [RED] Write unit tests: returns only unfilled applicable dims, empty when all filled, blocking severity for high-weight gaps (2026-04-17 — test_completeness_service.py: 3 tests)
- [x] [GREEN] Implement `GapService` in `application/services/completeness_service.py` (2026-04-16)
- [ ] Implement `domain/quality/gap_messages.py` — static dict (gap messages currently inline in dimension_checkers.py; deferred)

### Cache Invalidation Hooks

- [x] [RED] Write test: `SectionService.update_section()` calls cache.delete(completeness:{work_item_id}) (2026-04-17 — test_section_service_cache.py)
- [x] [GREEN] Hook cache invalidation in `SectionService.update_section()` (2026-04-17)
- [ ] [RED] Write test: `WorkItemService.transition_state()` invalidates completeness cache
- [ ] [GREEN] Hook cache invalidation in `WorkItemService.transition_state()` post-commit — deferred
- [ ] [GREEN] Hook cache invalidation in `ValidatorService.update_status()` post-commit — deferred

---

## Phase 6 — Next-Step Recommender

### NextStepDecisionTree

- [x] [RED] Write tests — 16 tests covering all 9 rules (assign_owner, improve_content, fill_blocking_gaps, submit_for_clarification, submit_for_review, address_warnings, assign_validators, export_or_wait, exported→null) (2026-04-17 — test_next_step_rules.py)
- [x] [GREEN] Implement `domain/quality/next_step_rules.py` — `evaluate(work_item, completeness, gaps) -> NextStepResult` pure function, ordered rule list (2026-04-17)

### ValidatorSuggestionEngine

- [ ] [RED] Write tests: deferred (ValidatorSuggestionEngine not implemented — out of scope for this pass)
- [ ] [GREEN] Implement `domain/quality/validator_suggestion_engine.py` — deferred

### Validator Role Config

- [ ] [RED] Deferred
- [ ] [GREEN] Deferred

### NextStepService

- [x] [RED+GREEN] Implement `application/services/next_step_service.py` — `recommend(work_item_id) -> NextStepResult` (2026-04-17)
- [x] `GET /api/v1/work-items/{id}/next-step` controller wired (`next_step_controller.py`, `main.py`, `dependencies.py`) (2026-04-17)

---

## Phase 7 — Specification Service

- [ ] [RED] Write unit tests using `FakeLLMAdapter` + fake repos:
  - `generate(work_item_id)`: returns correct sections for Bug type (all 8 sections per catalog)
  - `generate(work_item_id)`: returns correct sections for all 8 element types
  - Re-generation: skips sections with `generation_source='manual'` unless `force=True`
  - Re-generation with `force=True`: overwrites manual sections
  - `generate` with no work item content raises `SpecGenerationNoContentError`
  - Concurrent generation: Redis lock prevents simultaneous calls, returns `SPEC_GENERATION_IN_PROGRESS`
- [ ] [RED] Write unit tests for `save_section()`:
  - `version` incremented on save
  - `generation_source` set to `'manual'`
  - Empty content on required section raises `RequiredSectionEmptyError`
  - Empty content on optional section succeeds
  - Non-owner receives `ForbiddenError`
- [ ] [RED] Write unit tests for `bulk_save()`:
  - All sections saved atomically
  - One invalid section in batch rejects entire batch (all-or-nothing)
- [ ] [RED] Write unit tests for `revert_section()`:
  - New version created with `generation_source='revert'` and `revert_from_version` set
  - Revert to non-existent version raises `SectionVersionNotFoundError`
- [ ] [RED] Write unit tests: LLM prompt rendered correctly per element type (verify Jinja2 template receives correct context)
- [ ] [GREEN] Implement `application/services/specification_service.py`
- [ ] Wire LLM adapter: use `specification_generation` prompt template from `PromptRegistry`; parse structured JSON response into section content map

### Version Snapshot via VersioningService

**Single-writer invariant**: `SectionService.update_section()` and `bulk_save()` MUST call `VersioningService.create_version(work_item_id, trigger='section_edit', actor_id, actor_type='human')` instead of INSERTing into `work_item_versions` directly. EP-07's `VersioningService` is the sole owner of all writes to `work_item_versions` — no service in any other epic may bypass this.

- [ ] [RED] Write integration test: `SectionService.save_section()` calls `VersioningService.create_version()` (not INSERT directly); verify via `FakeVersioningService` that `create_version` is invoked with correct trigger and actor
- [ ] [RED] Write integration test: section save creates both a `work_item_section_versions` row (via SectionService) AND a `work_item_versions` row (via VersioningService) in the same DB transaction; if either fails, neither is committed
- [ ] [GREEN] In `SectionService.save_section()` and `bulk_save()`: call injected `IVersioningService.create_version()` after committing section changes — never INSERT to `work_item_versions` directly

---

## Phase 8 — Controllers

### SpecificationController

- [ ] [RED] Write integration tests (fake service layer):
  - `GET /specification` → 200 with sections array in `display_order`
  - `POST /specification/generate` → 200 with generated sections
  - `POST /specification/generate` → 409 `SPEC_GENERATION_IN_PROGRESS` when concurrent lock held
  - `PATCH /sections/{id}` → 200 on valid update, 422 on empty required section, 403 on non-owner
  - `PATCH /sections` (bulk) → 200 on valid batch, 422 if any section invalid (all rejected)
  - `GET /sections/{id}/versions` → 200 with version history array
- [ ] [GREEN] Implement `presentation/controllers/specification_controller.py`

### CompletenessController

- [ ] [RED] Write integration tests:
  - `GET /completeness` → 200 with score, level, dimensions array, `cached` flag
  - `GET /gaps` → 200 with gap list; 200 with empty list when no gaps
  - 403 on unauthorized access
- [ ] [GREEN] Implement `presentation/controllers/completeness_controller.py`

### NextStepController

- [ ] [RED] Write integration tests:
  - `GET /next-step` → 200 with `next_step`, `message`, `blocking`, `suggested_validators`
  - Exported item → `next_step=null` in response
  - 403 on unauthorized access
- [ ] [GREEN] Implement `presentation/controllers/next_step_controller.py`

### Acceptance Criteria — Controllers (Phase 8)

See also: specs/specification/spec.md (US-040, US-041), specs/quality-engine/spec.md (US-042, US-043)

**GET /api/v1/work-items/{id}/specification**
WHEN called for a work item with existing sections
THEN response is HTTP 200 with `{ "data": { "work_item_id": "uuid", "sections": [...] } }`
AND sections are ordered by `display_order` ascending

WHEN called for a work item with no sections
THEN response is HTTP 200 with `{ "data": { "sections": [] } }`

WHEN called by a user without read access
THEN response is HTTP 403

**POST /api/v1/work-items/{id}/specification/generate**
WHEN called for a work item with source content
THEN response is HTTP 200 with sections for that element type

WHEN called while another generation is running (Redis lock held)
THEN response is HTTP 409 `{ "error": { "code": "SPEC_GENERATION_IN_PROGRESS", "details": { "retry_after": N } } }`

WHEN called for a work item with no content (empty description, no conversation)
THEN response is HTTP 422 `{ "error": { "code": "SPEC_GENERATION_NO_CONTENT" } }`

**PATCH /api/v1/work-items/{id}/sections/{section_id}**
WHEN called with valid content by the owner
THEN response is HTTP 200 with updated section including incremented `version` and `generation_source: "manual"`

WHEN called with empty content on a required section
THEN response is HTTP 422 `{ "error": { "code": "REQUIRED_SECTION_EMPTY" } }`

WHEN called by a non-owner user
THEN response is HTTP 403 `{ "error": { "code": "SPEC_EDIT_FORBIDDEN" } }`

**PATCH /api/v1/work-items/{id}/sections (bulk)**
WHEN batch contains one section with empty content on a required field
THEN response is HTTP 422 identifying the failing section ID
AND NO sections from the batch are saved (all-or-nothing)

**GET /api/v1/work-items/{id}/completeness**
WHEN called successfully
THEN response is HTTP 200 with `{ "data": { "score": 0-100, "level": "low|medium|high|ready", "dimensions": [...], "cached": true|false } }`
AND `dimensions` array `weight` values sum to 1.0 (after renormalization)

WHEN called by a user without read access
THEN response is HTTP 403 `{ "error": { "code": "COMPLETENESS_ACCESS_FORBIDDEN" } }`

**GET /api/v1/work-items/{id}/gaps**
WHEN all applicable dimensions are filled
THEN response is HTTP 200 with `{ "data": [] }` (empty array)

WHEN some dimensions are unfilled
THEN response contains only unfilled applicable dimensions
AND blocking gaps appear before warnings in the array

**GET /api/v1/work-items/{id}/next-step**
WHEN work item state is `exported`
THEN response is HTTP 200 with `{ "data": { "next_step": null, "message": "This item has been exported to Jira." } }`

WHEN owner is not assigned
THEN response is HTTP 200 with `{ "data": { "next_step": "assign_owner", "blocking": true } }`

WHEN called for a work item the user cannot access
THEN response is HTTP 403

---

## Phase 9 — Error Middleware Extensions

- [ ] Add: `RequiredSectionEmptyError → 422 REQUIRED_SECTION_EMPTY`
- [ ] Add: `SpecGenerationNoContentError → 422 SPEC_GENERATION_NO_CONTENT`
- [ ] Add: `SpecGenerationInProgressError → 409 SPEC_GENERATION_IN_PROGRESS`
- [ ] Add: `SectionVersionNotFoundError → 404 SECTION_VERSION_NOT_FOUND`

---

## Definition of Done

- [ ] All tests pass (unit + integration)
- [ ] `mypy --strict` clean
- [ ] `ruff` clean
- [ ] `SECTION_CATALOG` has 100% coverage of all 8 element types with correct required/optional flags
- [ ] Completeness cache invalidated on section save (verified in integration test)
- [ ] Dual-write (section version + work item version) is atomic (verified via intentional failure injection)
- [ ] All 8 completeness endpoints return correct response shapes
- [ ] `work_item_versions` table populated after every section save
