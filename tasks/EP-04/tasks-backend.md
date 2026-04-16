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
- POST `/work-items/{id}/specification/generate` (Dundun `wm_spec_gen_agent` dispatch) — needs the same Celery + callback plumbing used by EP-03 suggestions
- PATCH `/work-items/{id}/sections` bulk endpoint
- GET `/work-items/{id}/sections/{section_id}/versions` history endpoint
- `NextStepService` + GET `/work-items/{id}/next-step`
- `ValidatorSuggestionEngine`
- Cache invalidation hooks in `SectionService.update_section`, `WorkItemService.transition_state`, `ValidatorService.update_status` (currently `CompletenessService.invalidate` exists but is not called from other services)
- Full CRUD on validators (assign/revoke/respond endpoints)
- Wiring SectionVersion-per-edit into `VersioningService.create_version` (EP-07's VersioningService is not implemented yet — when it lands, `SectionService.update_section` must call it so the `work_item_versions` snapshot is written)

## Phase 4 — Quality Engine: Dimension Checkers

All dimension checkers are pure functions: `(WorkItem, list[Section], list[Validator]) -> DimensionResult`. No I/O.

- [ ] [RED] Write tests for `check_problem_clarity()`: filled when `summary` + `context` combined >= 100 chars; not filled below threshold; returns `applicable=False` for Task, Sub-task, Spike
- [ ] [RED] Write tests for `check_objective()`: filled when `objective` section non-empty >= 50 chars; triangulate with 3 inputs: 0 chars, 49 chars, 50 chars
- [ ] [RED] Write tests for `check_scope()`: applicable for Initiative, Epic, Feature; not applicable for Bug, Task, Spike
- [ ] [RED] Write tests for `check_acceptance_criteria()`: filled when section has >= 2 bullet points (lines starting with `-` or `*`); 1 bullet does not count; applicable for User Story, Bug, Enhancement
- [ ] [RED] Write tests for `check_dependencies()`: filled when `dependencies` section non-empty OR content = "none" (case-insensitive); empty section is not filled
- [ ] [RED] Write tests for `check_risks()`: same pattern as `check_dependencies()`
- [ ] [RED] Write tests for `check_breakdown()`: filled when `breakdown` section has >= 1 line; applicable for Initiative, Epic, Feature
- [ ] [RED] Write tests for `check_ownership()`: filled when `work_item.owner_id` is set and `work_item.owner_suspended_flag = False`
- [ ] [RED] Write tests for `check_validations()`: filled when at least 1 `Validator` with status `approved` or `pending`; filled when `validation_status = 'acknowledged'` on work item
- [ ] [RED] Write tests for `check_next_step_clarity()`: filled when at least one other dimension returns a defined next step; not filled when all dimensions pass (item is ready)
- [ ] [GREEN] Implement all dimension checker functions in `domain/quality/dimension_checkers.py`
- [ ] [REFACTOR] 100% branch coverage on all dimension checkers; no imports from infrastructure layer

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

- [ ] [RED] Write unit tests for `ScoreCalculator.compute()`:
  - Weight renormalization: applicable dimensions' weights sum to 1.0
  - Score = 0 when all applicable dimensions unfilled
  - Score = 100 when all applicable dimensions filled
  - Inapplicable dimensions excluded and remaining weights renormalized
  - Band assignment: 0–39 = `low`, 40–69 = `medium`, 70–89 = `high`, 90–100 = `ready`
  - **WHEN all dimensions are inapplicable (total weight = 0.0) THEN score=0, level='low', dimensions=[] and no ZeroDivisionError is raised** (Fixed per backend_review.md ALG-4)
- [ ] [GREEN] Implement `domain/quality/score_calculator.py` — `ScoreCalculator.compute(dimension_results, work_item_type) -> CompletenessResult` and `renormalize_weights()`; guard: if `renormalize_weights` returns `{}` return `CompletenessResult(score=0, level='low', dimensions=[])`

### CompletenessCache

- [ ] [RED] Write tests for `CompletenessCache`: `get(work_item_id)` returns None on miss, `set` + `get` round-trip returns same value, `invalidate(work_item_id)` removes key
- [ ] [GREEN] Implement `infrastructure/cache/completeness_cache.py` — thin wrapper around Redis; cache key `completeness:{work_item_id}`, TTL 60 seconds

### CompletenessService

- [ ] [RED] Write unit tests using fake cache + fake repos:
  - Cache hit: skips DB calls entirely (verify fake repo not called)
  - Cache miss: calls `SectionRepository`, `ValidatorRepository`, `WorkItemRepository`, runs dimension checkers, populates cache
  - Result `dimensions` array contains correct `DimensionResult` entries
  - `cached: true` flag set when served from cache
- [ ] [GREEN] Implement `application/services/completeness_service.py` — `compute(work_item_id) -> CompletenessResult`

### GapService

- [ ] [RED] Write unit tests:
  - Returns only unfilled, applicable dimensions
  - Blocking gaps ordered before warnings before info
  - Empty list returned when all dimensions filled
  - Gap messages are static strings (not LLM-generated) from `domain/quality/gap_messages.py`
- [ ] [GREEN] Implement `application/services/gap_service.py` — `list(work_item_id) -> list[GapResult]`
- [ ] Implement `domain/quality/gap_messages.py` — static `dict[str, str]` mapping dimension name to human-readable gap message

### Cache Invalidation Hooks

- [ ] [RED] Write test: `SectionService.save()` calls `CompletenessCache.invalidate(work_item_id)` after DB commit
- [ ] [GREEN] Hook cache invalidation in `SectionService.save()` as post-commit callback
- [ ] [RED] Write test: `WorkItemService.transition_state()` invalidates completeness cache
- [ ] [GREEN] Hook cache invalidation in `WorkItemService.transition_state()` post-commit
- [ ] [GREEN] Hook cache invalidation in `ValidatorService.update_status()` post-commit

---

## Phase 6 — Next-Step Recommender

### NextStepDecisionTree

- [ ] [RED] Write tests — one test per rule, at minimum:
  - `owner=None` → `assign_owner` (highest priority, fires before all other rules)
  - `completeness_score < 30` → `improve_content`
  - All blocking gaps present → `fill_blocking_gaps` with `gaps_referenced`
  - State = `draft` + completeness >= 30 → `submit_for_clarification`
  - State = `in_clarification` + all required sections filled → `submit_for_review`
  - At least 1 warning gap unfilled → `address_warnings`
  - No validators assigned → `assign_validators`
  - State = `ready` → `export_or_wait` (no blocking next step)
  - State = `exported` → `null` (no next step)
  - Fallback: `complete_specification` when no other rule matches
- [ ] [GREEN] Implement `domain/quality/next_step_rules.py` — `NextStepDecisionTree.evaluate(work_item, completeness, gaps) -> NextStepResult`

### ValidatorSuggestionEngine

- [ ] [RED] Write tests:
  - Bug → `qa_engineer` (required), `tech_lead` (optional)
  - User Story → `product_owner` (required), `tech_lead` (optional)
  - Epic → `product_owner` (required), `tech_lead` (required), `stakeholder` (optional)
  - All 8 element types covered
  - Unconfigured role: `configured=False` + `setup_hint="Configure this role in workspace settings."`
- [ ] [GREEN] Implement `domain/quality/validator_suggestion_engine.py`

### Validator Role Config

- [ ] [RED] Write tests: `ValidatorRolesConfig` loads from YAML fixture successfully, missing config file returns empty mapping without raising
- [ ] [GREEN] Implement `infrastructure/config/validator_roles.py` — loads `validator_roles.yaml` at startup; `get_configured_roles(workspace_id) -> dict[str, str]` returns `{role: user_id | None}`

### NextStepService

- [ ] [RED] Write unit tests:
  - Result structure matches `GET /next-step` response shape
  - `blocking=True` when blocking gaps present
  - `suggested_validators` populated in all responses
  - Exported item returns `next_step=null`
- [ ] [GREEN] Implement `application/services/next_step_service.py` — `recommend(work_item_id) -> NextStepResult`

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
