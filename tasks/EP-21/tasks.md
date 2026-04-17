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
- [ ] Implementation
- [ ] code-review
- [ ] review-before-push

## Items

| ID | Title | Layer | Wave | Status |
|----|-------|-------|------|--------|
| F-1 | Layout widths — reclaim wide-monitor space | Frontend | 1 | [ ] |
| F-2 | Dev seed → populate inbox | Backend | 1 | [x] wired seed_notifications into seed_sample_data.py; 6 unit tests in test_seed_inbox.py |
| F-3 | Frontend refresh after mutation | Frontend | 2 | [ ] |
| F-4-be | Error envelope (backend: registry + middleware) | Backend | 1 | [x] domain/errors/codes.py registry + DomainError hierarchy; error_envelope.py middleware; tag_controller uses TagNameTakenError; 12 unit tests |
| F-4-fe | Error envelope (frontend: ApiError + field mapping) | Frontend | 2 | [ ] |
| F-5 | Edit work item modal | Frontend | 3 | [ ] |
| F-6 | Dundun fake HTTP service | Backend / Infra | 1 | [x] FakeDundunClient promoted to app/infrastructure/fakes/; infra/dundun-fake/ FastAPI app; wired into docker-compose.dev.yml; 9 integration tests |
| F-7 | User menu dropdown | Frontend | 1 | [ ] |
| F-8 | Matrix entry cascade | Frontend | 1 | [ ] |
| F-9 | Color picker component | Frontend | 1 | [ ] |
| F-10 | Edit tag modal | Frontend | 3 | [ ] |

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
| Wave 1 implementation | In progress |
| Wave 2 implementation | Pending Wave 1 |
| Wave 3 implementation | Pending Wave 2 |
| Reviews | Pending |

## Evidence

- `frontend/hooks/use-teams.ts:55-60` — `addMember` does not update local state after POST (F-3, confirmed)
- `frontend/app/workspace/[slug]/**/page.tsx` — all pages use `max-w-4xl/5xl/6xl/7xl` (F-1, confirmed)
- `backend/tests/fakes/fake_dundun_client.py:33` — `FakeDundunClient` class exists, ready to wrap in HTTP (F-6)
- `backend/app/presentation/controllers/work_item_controller.py` — `PATCH /work-items/{id}` endpoint exists (F-5, frontend-only work)
- `frontend/components/workspace/workspace-sidebar.tsx:91-98` — theme toolbar crammed above user footer (F-7)
- `frontend/app/workspace/[slug]/admin/page.tsx:538-544` — tag color is a plain hex text input (F-9)
- `backend/app/presentation/controllers/tag_controller.py:136` — `PATCH /tags/{id}` exists; frontend only uses it for archive (F-10)
