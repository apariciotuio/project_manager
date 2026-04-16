# EP-02 — Implementation Checklist

Branch: `feature/EP-02-backend` / `feature/EP-02-frontend`
Refs: EP-02

---

## Phase 1 — Database Migrations

- [ ] Write migration: add `draft_data JSONB` and `template_id UUID` columns to `work_items`
- [ ] Write migration: create `work_item_drafts` table with UNIQUE constraint and expiry index
- [ ] Write migration: create `templates` table with system/workspace unique indexes and CHECK constraints
- [ ] Verify all indexes created (template lookup, draft expiry, work_items template ref)

---

## Phase 2 — Domain Layer (Python)

- [ ] [RED] Write tests for `WorkItemDraft` dataclass: construction, field types, expiry default
- [ ] [GREEN] Implement `domain/models/work_item_draft.py`
- [ ] [RED] Write tests for `Template` dataclass: system flag + workspace_id mutual exclusion, content length enforcement
- [ ] [GREEN] Implement `domain/models/template.py`
- [ ] [RED] Write tests for `WorkItem` dataclass extensions: `draft_data` cleared on state advance out of Draft, `template_id` immutable after set
- [ ] [GREEN] Extend `domain/models/work_item.py` with `draft_data` and `template_id` fields
- [ ] [REFACTOR] Review domain models for clarity and invariant completeness

---

## Phase 3 — Repository Layer

- [ ] [RED] Write tests for `WorkItemDraftRepository`: upsert conflict (version check), get by user+workspace, delete, expiry query
- [ ] [GREEN] Implement `infrastructure/persistence/work_item_draft_repository.py`
- [ ] [RED] Write tests for `TemplateRepository`: get by workspace+type, get system default, precedence logic, create/update/delete
- [ ] [GREEN] Implement `infrastructure/persistence/template_repository.py`
- [ ] [RED] Write tests for `WorkItemRepository` additions: save/load `draft_data` and `template_id` columns
- [ ] [GREEN] Extend `infrastructure/persistence/work_item_repository.py`

---

## Phase 4 — Application Services

- [ ] [RED] Write tests for `DraftService.upsert_pre_creation_draft`: happy path, version conflict returns `DraftConflict`, version match upserts
- [ ] [RED] Write tests for `DraftService.save_committed_draft`: valid Draft state saves, non-Draft state raises `InvalidStateError`
- [ ] [RED] Write tests for `DraftService.discard_pre_creation_draft`: deletes record, 404 if not owned by user
- [ ] [GREEN] Implement `application/services/draft_service.py`
- [ ] [RED] Write tests for `TemplateService.get_template_for_type`: workspace override, system fallback, none found returns None
- [ ] [RED] Write tests for `TemplateService.create_template`: admin-only gate, duplicate type raises, content too long raises
- [ ] [RED] Write tests for `TemplateService.update_template`: admin-only, system template raises `Forbidden`
- [ ] [RED] Write tests for `TemplateService.delete_template`: admin-only, system template raises `Forbidden`
- [ ] [GREEN] Implement `application/services/template_service.py`
- [ ] [REFACTOR] Check service layer for N+1 queries and missing cache invalidation

---

## Phase 5 — API Controllers

- [x] All controllers + integration tests — see `tasks-backend.md` Phase 6 for the full per-route breakdown (13 draft + 10 template integration tests, all green 2026-04-16)
- [x] `POST /api/v1/work-items` accepts optional `template_id` (stored via `CreateWorkItemCommand`)
- [x] [REFACTOR] Private `_repo` access + inline `HTTPException` for mapped exceptions removed; all domain exceptions bubble to global `error_middleware.py`
- [x] Test infra: `get_cache_adapter` dep extracted; `FakeCache` override in `conftest.py` + `test_template_controller.py::app` fixture

**Status: COMPLETED** (2026-04-16)

---

## Phase 6 — Background Job

- [x] [RED] 4 unit tests + 3 integration tests for `expire_work_item_drafts` — see `tests/unit/infrastructure/jobs/test_expire_drafts.py` + `tests/integration/test_expire_drafts_job.py`
- [x] [GREEN] `infrastructure/jobs/expire_drafts_task.py` + `DraftService.expire_pre_creation_drafts`
- [x] Registered in Celery Beat: `expire-work-item-drafts-daily` at `crontab(hour=2, minute=0)` in `app/config/celery_app.py`

**Status: COMPLETED** (2026-04-16)

---

## Phase 7 — Redis Caching

- [x] Cache layer in `TemplateService.get_template_for_type` — 2026-04-15 (keys `template:{workspace_id}:{type}` / `template:system:{type}`, TTL 300s)
- [x] Invalidation on `create_template`, `update_template`, `delete_template`
- [x] [RED] Unit tests verifying cache hit avoids DB call, miss falls through — 2026-04-15

**Status: COMPLETED** (2026-04-15, reinforced 2026-04-16 with DI cleanup)

---

## Phase 8 — Frontend: useAutoSave Hook

- [ ] [RED] Write tests for `useAutoSave`: debounce fires after 3s, does not fire during rapid typing, calls save with latest data, handles 409 by calling onConflict
- [ ] [GREEN] Implement `hooks/useAutoSave.ts`
- [ ] [REFACTOR] Verify the hook is side-effect-free on unmount (clears debounce timer)

---

## Phase 9 — Frontend: CaptureForm Component

- [ ] [RED] Write component tests for `CaptureForm`: renders empty, SubmitButton disabled when title < 3 chars, DraftResumeBanner shown when draft exists, TypeSelector triggers template fetch
- [ ] [RED] Write tests for type change flow: confirmation modal shown when description non-empty, template replaces description on confirm, reverts on cancel
- [ ] [GREEN] Implement `components/CaptureForm/CaptureForm.tsx` with sub-components
- [ ] [GREEN] Implement `components/CaptureForm/DraftResumeBanner.tsx`
- [ ] [GREEN] Implement `components/CaptureForm/StalenessWarning.tsx`
- [ ] Wire `useAutoSave` into `CaptureForm`
- [ ] Wire template fetch (React Query, staleTime 5 min) on type selection change

---

## Phase 10 — Frontend: WorkItemHeader Extensions

- [ ] [RED] Write component tests for `WorkItemHeader`: renders type badge, state chip, owner with suspended warning, completeness bar, NextStepHint when score < 30
- [ ] [GREEN] Extend `components/WorkItemHeader/WorkItemHeader.tsx` with completeness bar and NextStepHint
- [ ] [GREEN] Implement owner initials fallback when `avatar_url` is null
- [ ] Verify header renders correctly immediately from POST /work-items 201 response (no second fetch)

---

## Phase 11 — Review Gates

- [ ] Run full backend test suite — all green
- [ ] Run frontend test suite — all green
- [ ] Run linter + type checks (mypy strict, tsc --noEmit)
- [ ] `code-reviewer` agent review
- [ ] `review-before-push` workflow
- [ ] User confirmation before git push

---

## Progress Legend

- `[ ]` — not started
- `[x]` — completed (add date + brief note)
- `[~]` — in progress
- `[!]` — blocked (add reason)

**Backend Status: COMPLETED** (2026-04-16) — Phases 1-7 green, 557 tests pass, 93% coverage
**Frontend Status: NOT STARTED** — Phases 8-11 pending
