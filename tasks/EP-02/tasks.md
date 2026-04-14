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

- [ ] [RED] Write integration tests for `POST /api/v1/work-item-drafts`: upsert, 409 on version conflict, response includes draft_id + local_version
- [ ] [RED] Write integration tests for `GET /api/v1/work-item-drafts`: returns current draft or null
- [ ] [RED] Write integration tests for `DELETE /api/v1/work-item-drafts/{id}`: deletes, 403 if not owner
- [ ] [GREEN] Implement `presentation/controllers/work_item_draft_controller.py` + routes
- [ ] [RED] Write integration tests for `PATCH /api/v1/work-items/{id}/draft`: valid Draft state saves, 409 if non-Draft, 401 if unauthenticated, 403 if not owner
- [ ] [GREEN] Implement PATCH `/work-items/{id}/draft` route (add to work item controller)
- [ ] [RED] Write integration tests for `GET /api/v1/templates`: returns workspace override or system default, 401 unauthenticated
- [ ] [RED] Write integration tests for `POST /api/v1/templates`: admin creates, non-admin 403, duplicate type 409, content too long 422
- [ ] [RED] Write integration tests for `PATCH /api/v1/templates/{id}`: admin updates, system template 403, non-admin 403
- [ ] [RED] Write integration tests for `DELETE /api/v1/templates/{id}`: admin deletes, system template 403
- [ ] [GREEN] Implement `presentation/controllers/template_controller.py` + routes
- [ ] Verify `POST /api/v1/work-items` passes `template_id` through to service (extend EP-01 controller)
- [ ] [REFACTOR] Audit all new endpoints: auth check, authz check, input validation at boundary

---

## Phase 6 — Background Job

- [ ] [RED] Write tests for draft expiry Celery task: selects drafts where expires_at < now(), soft-deletes them
- [ ] [GREEN] Implement `infrastructure/jobs/expire_drafts_task.py`
- [ ] Register task in Celery beat schedule (daily at 02:00 UTC)

---

## Phase 7 — Redis Caching

- [ ] Add cache layer to `TemplateService.get_template_for_type`: key `template:{workspace_id}:{type}` / `template:system:{type}`, TTL 5 minutes
- [ ] Invalidate cache on `create_template`, `update_template`, `delete_template`
- [ ] [RED] Write tests verifying cache hit avoids DB call, cache miss falls through to DB

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

**Status: NOT STARTED**
