# EP-21 — Post-MVP Feedback Batch

Bundle of 10 items from first manual QA round (2026-04-17).

## Artifacts

- [x] `proposal.md` — scope, stories, AC per item
- [x] `design.md` — decisions D-1..D-10
- [x] `specs/responsive-layout/spec.md` — F-1
- [x] `specs/dev-seed-inbox/spec.md` — F-2
- [x] `specs/mutation-refresh/spec.md` — F-3
- [x] `specs/error-envelope/spec.md` — F-4
- [x] `specs/work-item-edit/spec.md` — F-5
- [x] `specs/dundun-fake-service/spec.md` — F-6
- [x] `specs/user-menu/spec.md` — F-7
- [x] `specs/matrix-entry-cascade/spec.md` — F-8
- [x] `specs/color-picker/spec.md` — F-9
- [x] `specs/tag-edit/spec.md` — F-10
- [x] Implementation
- [x] code-review (3 MF + 7 SF + 5 N — all closed)
- [ ] review-before-push

## Items

| ID | Title | Layer | Wave | Status |
|----|-------|-------|------|--------|
| F-1 | Layout widths — reclaim wide-monitor space | Frontend | 1 | [x] PageContainer variant="wide|narrow" in components/layout/page-container.tsx; 4 wide pages (items, item-detail, admin, teams) + 2 narrow (inbox, new-item) migrated; 9 unit tests |
| F-2 | Dev seed → populate inbox | Backend | 1 | [x] wired seed_notifications into seed_sample_data.py; 6 unit tests in test_seed_inbox.py |
| F-3 | Frontend refresh after mutation | Frontend | 2 | [x] useTeams.addMember re-fetches list after 2xx; isPendingMutation flag disables button; 2 new hook tests (addMember updates list, error leaves state unchanged) |
| F-4-be | Error envelope (backend: registry + middleware) | Backend | 1 | [x] domain/errors/codes.py registry + DomainError hierarchy; error_envelope.py middleware; tag_controller uses TagNameTakenError; 12 unit tests |
| F-4-fe | Error envelope (frontend: ApiError + field mapping) | Frontend | 2 | [x] ApiError.field + fromResponse; lib/errors/{api-error,codes,use-form-errors,toast}.ts; TagsTab maps TAG_NAME_TAKEN to input error; teams addMember uses handleApiError; 25 new tests; admin-page +1 |
| F-5 | Edit work item modal | Frontend | 3 | [x] WorkItemEditModal (title/desc/priority/type, diff PATCH, field errors, Save disabled when no change); Edit button on detail page (owner + superadmin); 12 modal tests + 2 detail-page tests; commit 781dccc |
| F-6 | Dundun fake HTTP service | Backend / Infra | 1 | [x] FakeDundunClient promoted to app/infrastructure/fakes/; infra/dundun-fake/ FastAPI app; wired into docker-compose.dev.yml; 9 integration tests |
| F-7 | User menu dropdown | Frontend | 1 | [x] Radix DropdownMenu behind avatar trigger; ThemeSwitcher+Matrix+Rain+Settings+SignOut; sidebar toolbar removed; 19 tests in user-menu.test.tsx; layout.test.tsx updated |
| F-8 | Matrix entry cascade | Frontend | 1 | [x] full-viewport canvas overlay (z:9999, pointer-events:none); 10-15 phosphor-green katakana columns, ~1.2s RAF loop; reduced-motion skip; RAF cleanup on abort; wired into UserMenu.handleMatrixToggle; 14 tests |
| F-9 | Color picker component | Frontend | 1 | [x] components/ui/color-picker.tsx; 12 presets, custom hex + 150ms debounce, validation, keyboard nav, aria-radiogroup; 21 unit tests; 0 new deps |
| F-10 | Edit tag modal | Frontend | 3 | [x] TagEditModal (name + ColorPicker, diff PATCH, TAG_NAME_TAKEN field error, archived indicator, Save disabled when no change); Pencil icon per tag row; replaceTag() in useTags for local state update; 9 modal tests + 3 admin-page tests; commit 33d2217 |

## Implementation Waves

**Wave 1 — 3 parallel agents (no file overlap):**
- Agent A (backend-developer): F-2 + F-4-be + F-6
- Agent B (frontend-developer): F-1 + F-9
- Agent C (frontend-developer): F-7 + F-8

**Wave 2 — 1 agent (depends on Wave 1 Agent A for F-4-be):**
- Agent D (frontend-developer): F-4-fe + F-3

**Wave 3 — 1 agent (depends on Waves 1+2):**
- Agent E (frontend-developer): F-5 + F-10

## Rules for each agent

- TDD mandatory: RED → GREEN → REFACTOR per spec scenario
- Update this file (`tasks/EP-21/tasks.md`) after each item: `[ ]` → `[x]` with brief note
- Conventional commits with `Refs: EP-21`, one commit per logical step
- DO NOT push to remote
- Run tests + lint + typecheck before reporting back
- If blocked, log to `tasks/EP-21/blockers.md` and surface

## Progress

| Phase | Status |
|-------|--------|
| Proposal | **COMPLETED** (2026-04-17) |
| Specs / Design | **COMPLETED** (2026-04-17) |
| Wave 1 implementation | **COMPLETED** (2026-04-17) |
| Wave 2 implementation | **COMPLETED** (2026-04-17) |
| Wave 3 implementation | **COMPLETED** (2026-04-17) |
| Reviews | **COMPLETED** (2026-04-17) — all MF/SF/N closed |

## Evidence

- `frontend/hooks/use-teams.ts:55-60` — `addMember` does not update local state after POST (F-3, confirmed)
- `frontend/app/workspace/[slug]/**/page.tsx` — all pages use `max-w-4xl/5xl/6xl/7xl` (F-1, confirmed)
- `backend/tests/fakes/fake_dundun_client.py:33` — `FakeDundunClient` class exists, ready to wrap in HTTP (F-6)
- `backend/app/presentation/controllers/work_item_controller.py` — `PATCH /work-items/{id}` endpoint exists (F-5, frontend-only work)
- `frontend/components/workspace/workspace-sidebar.tsx:91-98` — theme toolbar crammed above user footer (F-7)
- `frontend/app/workspace/[slug]/admin/page.tsx:538-544` — tag color is a plain hex text input (F-9)
- `backend/app/presentation/controllers/tag_controller.py:136` — `PATCH /tags/{id}` exists; frontend only uses it for archive (F-10)
