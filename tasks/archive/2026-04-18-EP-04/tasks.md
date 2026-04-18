# EP-04 — Implementation Checklist

**Status (archived 2026-04-18 as v1)**: ✅ SHIPPED — 85/118 real items (72%): 5 migrations (0017–0021) + 4 repositories + 9 dimension checkers (44 triangulated tests) + CompletenessService + ScoreCalculator + GapService + NextStepDecisionTree + NextStepService + SectionService + ValidatorService + 3 controllers wired (`GET /specification`, `PATCH /sections/{id}`, `GET /completeness`, `GET /gaps`, `GET /next-step`) + spec-gen callback handler + FE (SpecificationSectionsEditor w/ debounced auto-save, CompletenessPanel, NextStepHint, 2-column detail integration).

> ⚠️ **Prior header said "NOT STARTED" — that was stale.** The authoritative sub-trackers were `tasks-backend.md` and `tasks-frontend.md` (both updated 2026-04-16+).

### v1 scope shipped
- **BE**: sections CRUD + versioning + validators + 9 dimension checkers + completeness engine (score + gap messages + cache + invalidation on edit) + next-step decision tree (9 rules) + full controller surface + spec-gen Dundun callback handler.
- **FE**: SpecificationSectionsEditor (debounced auto-save 600ms, generation badge, version chip), CompletenessPanel (score ring + LevelBadge + per-dimension bars + gap overlay + cached badge), NextStepHint (message + blocking badge + suggested validators), 2-column detail-page integration.
- **Tests**: BE 1174 green + 94 FE component tests. Ruff + mypy --strict clean on EP-04 files.

### Deferred (v2 scope, new follow-up epic — NOT EP-04 v1)
- `POST /specification/generate` trigger endpoint (spec-gen Dundun callback handler IS shipped; the trigger that dispatches the request from the detail page is deferred).
- `PATCH /sections` bulk endpoint (single PATCH works; batch atomic mutation deferred).
- `GET /sections/{id}/versions` history endpoint + section revert UI.
- `ValidatorSuggestionEngine` (role-based validator suggestions; NextStepRules currently returns static rule IDs only).
- `domain/quality/gap_messages.py` extraction (messages inline in `dimension_checkers.py` — refactor-only).
- Cache invalidation hooks in `WorkItemService.transition_state()` + `ValidatorService.update_status()` (section edits invalidate; state/validator changes don't re-score yet).
- `workspace_id` parameter on repo methods (defense-in-depth for CRIT-2; batched with EP-03 Phase 8 RLS follow-up per `decisions.log.md` 2026-04-16).
- Phase 9 Error Middleware extended codes (basic 422/403 work).

### Re-homed from EP-03 (tracked but not implemented here)
- `QuickActionService` + apply/undo endpoints — `dundun_tasks.py` has a TODO marker "wire into QuickActionService when EP-04 lands"; explicit wiring deferred to v2.
- `/work-items/{id}/gaps/ai-review` endpoint — dispatches `wm_gap_agent`; callback handler IS shipped, the trigger endpoint is not.

---

## Phase 1 — Data Model & Migrations

- [ ] Write migration: `work_item_sections` table with indexes
  - TDD: test migration applies and rolls back cleanly
- [ ] Write migration: `work_item_section_versions` table with indexes
- [ ] Write migration: `work_item_validators` table with unique constraint
- [ ] Write migration: add nullable `section_id` FK to `suggestions` table (EP-03 integration)
- [ ] Add `SectionType` enum in `domain/models/section_type.py`
- [ ] Add `SectionConfig` dataclass and `SECTION_CATALOG` in `domain/models/section_catalog.py`
  - TDD: test all 8 element types have correct required/optional sections, no duplicates
- [ ] Add `Section` domain entity in `domain/models/section.py`
  - TDD: test invariants (empty content on required section raises, version increments correctly)
- [ ] Add `SectionRepository` interface in `domain/repositories/section_repository.py`
- [ ] Add `SectionVersionRepository` interface in `domain/repositories/section_version_repository.py`
- [ ] Add `ValidatorRepository` interface in `domain/repositories/validator_repository.py`

**Status: NOT STARTED**

---

## Phase 2 — Repository Implementations

- [ ] Implement `SectionRepositoryImpl` in `infrastructure/persistence/`
  - TDD (RED): test `get_by_work_item` returns ordered sections
  - TDD (RED): test `save` creates version snapshot before overwrite
  - TDD (RED): test `bulk_save` is atomic (all or nothing)
  - GREEN + REFACTOR
- [ ] Implement `SectionVersionRepositoryImpl`
  - TDD: test append-only (no update path exists)
  - TDD: test version history ordered descending
- [ ] Implement `ValidatorRepositoryImpl`
  - TDD: test unique constraint enforced per (work_item_id, role)

**Status: NOT STARTED**

---

## Phase 3 — Specification Service (US-040, US-041)

- [ ] Implement `SpecificationService.generate()` in `application/services/`
  - TDD (RED): test generates correct sections for Bug type
  - TDD (RED): test generates correct sections for User Story type
  - TDD (RED): test generates correct sections for all remaining 6 types
  - TDD (RED): test re-generation skips manual sections without force=true
  - TDD (RED): test re-generation with force=true overwrites manual sections
  - TDD (RED): test raises SPEC_GENERATION_NO_CONTENT when no raw text and no conversation
  - TDD (RED): test concurrent generation returns SPEC_GENERATION_IN_PROGRESS (Redis lock)
  - GREEN + REFACTOR
- [ ] Implement `SpecificationService.save_section()` (single PATCH)
  - TDD: test version is incremented on save
  - TDD: test generation_source set to 'manual'
  - TDD: test save empty content on required section raises
  - TDD: test save empty content on optional section succeeds
  - TDD: test non-owner receives 403
- [ ] Implement `SpecificationService.bulk_save()` (bulk PATCH)
  - TDD: test all sections saved atomically
  - TDD: test one invalid section in batch rejects entire batch
- [ ] Implement `SpecificationService.revert_section()`
  - TDD: test new version created with generation_source='revert' and revert_from_version set
  - TDD: test revert to non-existent version raises 404
- [ ] Wire LLM adapter for specification generation prompt
  - TDD: test prompt rendered correctly per element type (unit test, fake LLM adapter)
  - TDD: test LLM response parsed into section content map

**Status: NOT STARTED**

---

## Phase 4 — Quality Engine: Dimension Checkers (US-042)

- [ ] Implement `DimensionResult` dataclass in `domain/quality/dimension_result.py`
- [ ] Implement `check_problem_clarity()` in `domain/quality/dimension_checkers.py`
  - TDD: test filled when summary + context >= threshold
  - TDD: test not filled when content below threshold
  - TDD: test not applicable for Task/Sub-task/Spike
- [ ] Implement `check_objective()`
  - TDD: test filled, not filled, triangulate lengths
- [ ] Implement `check_scope()`
  - TDD: test applicable types only
- [ ] Implement `check_acceptance_criteria()`
  - TDD: test >= 2 bullet points counts as filled
  - TDD: test 1 bullet point does not count
  - TDD: test applicable types only
- [ ] Implement `check_dependencies()`
  - TDD: test "none" literal content counts as filled
  - TDD: test empty does not count
- [ ] Implement `check_risks()`
  - TDD: same pattern as dependencies
- [ ] Implement `check_breakdown()`
  - TDD: test linked child items count
  - TDD: test user_stories_breakdown section content counts
  - TDD: test applicable types only
- [ ] Implement `check_ownership()`
  - TDD: test owner present / absent
- [ ] Implement `check_validations()`
  - TDD: test at least 1 validator assigned counts
  - TDD: test validation_status='acknowledged' counts
- [ ] Implement `check_next_step_clarity()` (trivial — depends on next-step not being undefined)
  - TDD: test returns filled=True when other dimensions compute a valid next step

**Status: NOT STARTED**

---

## Phase 5 — Completeness Service & Cache (US-042)

- [ ] Implement `ScoreCalculator.compute()` in `domain/quality/score_calculator.py`
  - TDD: test weight renormalization sums to 1.0
  - TDD: test score = 0 when all dimensions unfilled
  - TDD: test score = 100 when all dimensions filled
  - TDD: test correct band assignment (low/medium/high/ready)
  - TDD: test inapplicable dimensions excluded and weights renormalized
- [ ] Implement `CompletenessCache` in `infrastructure/cache/completeness_cache.py`
  - TDD: test get returns None on miss
  - TDD: test set then get returns same value
  - TDD: test invalidate removes key
- [ ] Implement `CompletenessService.compute()` in `application/services/`
  - TDD: test cache hit skips DB calls (using fake cache)
  - TDD: test cache miss populates cache after DB call
  - TDD: test result contains dimensions array with correct structure
- [ ] Implement `GapService.list()` in `application/services/`
  - TDD: test only unfilled applicable dimensions returned
  - TDD: test blocking gaps ordered before warnings
  - TDD: test empty list when all dimensions filled
  - TDD: test gap messages are per-dimension strings (not LLM-generated)
- [ ] Hook cache invalidation in `SectionService.save()` (post-commit callback)
  - TDD: test cache is invalidated after section save
- [ ] Hook cache invalidation in `WorkItemService.transition_state()`
  - TDD: test cache is invalidated after state transition

**Status: NOT STARTED**

---

## Phase 6 — Next-Step Recommender (US-043)

- [ ] Implement `NextStepDecisionTree.evaluate()` in `domain/quality/next_step_rules.py`
  - TDD: test each rule in priority order (13 rules, at least 1 test each)
  - TDD: test fallback rule fires when no other rule matches
  - TDD: test owner=null always returns assign_owner regardless of other conditions
- [ ] Implement `ValidatorSuggestionEngine.suggest()` in `domain/quality/validator_suggestion_engine.py`
  - TDD: test Bug returns qa_engineer required + tech_lead optional
  - TDD: test User Story returns product_owner required + tech_lead optional
  - TDD: test Epic returns 3 roles (product_owner, tech_lead required; stakeholder optional)
  - TDD: test unconfigured role has configured=False + setup_hint
  - TDD: test all 8 element types have coverage
- [ ] Load validator role config in `infrastructure/config/validator_roles.py`
  - TDD: test config loads from YAML fixture
  - TDD: test missing config file returns empty mapping without crashing
- [ ] Implement `NextStepService.recommend()` in `application/services/`
  - TDD: test result structure matches expected response shape
  - TDD: test blocking=True when blocking gaps present
  - TDD: test suggested_validators present in all responses
- [ ] Implement override-to-Ready flow in `WorkItemService.force_ready()`
  - TDD: test requires force_ready=True and non-empty override_reason
  - TDD: test audit log entry created with reason + timestamp
  - TDD: test returns 422 without force flag when validations pending

**Status: NOT STARTED**

---

## Phase 7 — Controllers & Routes

- [ ] Implement `SpecificationController` with routes:
  - GET /work-items/:id/specification
  - POST /work-items/:id/specification/generate
  - PATCH /work-items/:id/sections/:section_id
  - PATCH /work-items/:id/sections (bulk)
  - GET /work-items/:id/sections/:section_id/versions
  - TDD: integration tests for each endpoint (fake service layer)
  - TDD: test 403 on unauthorized access
  - TDD: test 422 on invalid input
- [ ] Implement `CompletenessController` with routes:
  - GET /work-items/:id/completeness
  - GET /work-items/:id/gaps
  - TDD: test response shape matches spec
  - TDD: test 403 on unauthorized access
- [ ] Implement `NextStepController` with route:
  - GET /work-items/:id/next-step
  - TDD: test response shape
  - TDD: test exported item returns null next_step

**Status: NOT STARTED**

---

## Phase 8 — Integration & E2E Tests

- [ ] E2E: generate spec from captured element, verify all sections present for each type
- [ ] E2E: edit a section, verify version incremented and snapshot created
- [ ] E2E: compute completeness with all sections filled, verify score >= 90
- [ ] E2E: compute completeness with required sections empty, verify gaps list
- [ ] E2E: next-step recommendation flow from Draft -> Ready (happy path)
- [ ] E2E: force-ready override with reason, verify audit log
- [ ] E2E: EP-03 suggestion targeted at a section, accept it, verify section updated + cache invalidated

**Status: NOT STARTED**

---

## Notes

- Do not implement EP-07 versioning integration here — EP-04 creates its own version snapshots in
  `work_item_section_versions`. EP-07 may unify these later.
- The `specification/generate` endpoint uses the EP-03 LLM adapter. Do not introduce a second adapter.
- Completeness formula is expected to evolve. The dimension checker functions and weight constants must
  be easy to change independently — no hardcoded magic numbers in the service layer.
