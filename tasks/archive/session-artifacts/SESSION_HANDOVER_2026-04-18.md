# Session Handover — 2026-04-18

Session led by **Tilly** (Opus 4.7). Successor agent can pick up from here without re-reading conversation history.

---

## 1. TL;DR for the next agent

- **10 commits on `main`** ahead of `origin/main`. **Nothing pushed yet** — user controls the push.
- Priority order executed: **EP-22 first**, then **close > open new**.
- EP-22 is code-complete (1 Must Fix + 4 Should Fix closed). External Dundun cross-repo PRs #1 + #2 still pending (FE degrades gracefully).
- EP-03 WU-3 (version conflict guard) shipped. EP-03 MF#1 (RLS) was ticket rot — already implemented.
- EP-07 FE Groups 1, 3a, 3b, 2 shipped (diff viewer + compare selector + comment hooks).
- EP-12 gained 3 closures: CORS startup validation, capability enforcement gate, `extra="forbid"` hardening.

## 2. Commits landed (newest first)

```
cf06aec feat(ep-07): FE diff viewer + comment hooks slice (Groups 1/3a/3b/2)
4becff9 feat(ep-12): enforce Pydantic extra=forbid on FE request schemas
f73f948 feat(ep-12): capability-based authorization gate for FastAPI routes
ebf2cf4 feat(ep-12,ep-03): CORS startup validation + RLS ticket rot cleanup
c21168c feat(ep-03): version conflict guard on suggestion apply (WU-3)
f77e9bc chore(ep-22,ep-03,ep-21): sync umbrella tasks.md after 2026-04-18 work
abf7015 fix(ep-22): cap suggested_sections + sanitize validation logs (SEC-INVAL-001, SEC-LOG-001)
ced46a7 fix(ep-22): enforce workspace_id scope on conversation threads (SEC-AUTH-001)
e88e1b6 fix(ep-22): require DUNDUN/PUPPET_SERVICE_KEY in production (SEC-CONF-001)
dd27ca6 docs(ep-22): resolve chat_ws spec drift — live transport on BE→Dundun hop
```

Diff stat across the 10: 41 files changed, ~3031 insertions, ~172 deletions (mostly code + tests; docs are the EP-22 `dundun-specifications.md` rewrite).

## 3. What's uncommitted on the branch (NOT from this session)

These were already modified when the session started. **Leave them alone unless the user asks** — they are cross-cutting work-in-progress not owned by this session.

```
M backend/app/infrastructure/persistence/tag_repository_impl.py
M backend/app/infrastructure/rate_limiting/pg_rate_limiter.py
M backend/app/main.py
M backend/apps/mcp_server/server.py
M backend/tests/unit/presentation/middleware/test_rate_limit.py
?? backend/apps/mcp_server/tools/list_tags.py
?? backend/tests/unit/presentation/mcp/test_list_tags_tool.py
?? tasks/archive/  (directory move already in progress by a parallel session)
D  tasks/EP-00/**, EP-01/**, EP-02/**, EP-05/**, EP-06/**, EP-15/**, EP-19/**, EP-20/**, M0/** (the archive move)
```

The deletions are the active archive migration into `tasks/archive/` — the user has a parallel workflow moving shipped EPs there. Don't stage those.

## 4. EP-by-EP state after this session

| EP | Before | After | Notes |
|---|---|---|---|
| **EP-03** | 77% BE, 74% FE | **~82% BE**, 74% FE | WU-3 (version conflict guard) + MF#1 RLS ticket rot + SF#9 (covered by EP-22) |
| **EP-07** | 80% BE, 31% FE | 80% BE, **~55% FE** | Groups 1+3a+3b+2 shipped (diff viewer + compare selector + comment hooks). Groups 4/5/6/7 remain. |
| **EP-12** | 78% BE, 84% FE | **~86% BE**, 84% FE | CORS validation + capability gate + `extra="forbid"` hardening + RLS docs. |
| **EP-21** | 10/10 items shipped | same, **RBP gate pending** | review-before-push section appended to tasks.md; gate not run. |
| **EP-22** | 91% BE, 83% FE | **code 100%** | 1 MF + 4 SF closed. Cross-repo Dundun PRs #1 (schema) + #2 (prompt) still needed — **external**, not blocking FE (degrades to no-op). |

## 5. Open questions / user decisions needed

1. **Push to `origin/main`** — all 10 commits are local. User gate per CLAUDE.md "NEVER `git push` without explicit user confirmation".
2. **Dundun cross-repo PR coordination** — PR #1 and #2 are in the `dundun` repo. Who's opening them? Action item sitting on EP-22 until someone does.
3. **EP-07 FE Group 5 (Timeline filters + tab)** — next natural slice per FE closure plan. Unblocked, M effort.
4. **EP-11 / EP-16 / EP-17 / EP-18** — still post-MVP per `tasks/attack_plan_2026-04-17.md`. Session did not touch them. Don't pull them back in without explicit user decision.

## 6. Tests landed in this session

| Layer | File | Tests |
|---|---|---|
| BE | `tests/unit/config/test_settings_production_required.py` | +7 (DUNDUN/PUPPET service_key + CORS) |
| BE | `tests/unit/application/test_conversation_service.py` | +4 (workspace scope) |
| BE | `tests/integration/test_conversation_controller.py` | +1 (cross-workspace → 404) |
| BE | `tests/integration/test_conversation_ws.py` | +1 (mismatched workspace → 4403) |
| BE | `tests/unit/presentation/test_dundun_signals.py` | +5 (list cap + log sanitisation) |
| BE | `tests/unit/application/test_suggestion_service_apply.py` | +4 (WU-3 version conflict) |
| BE | `tests/unit/presentation/test_require_capabilities.py` | +7 (capability gate, new file) |
| BE | `tests/unit/presentation/test_schemas_strict_extra.py` | +8 (extra=forbid / ignore, new file) |
| FE | `__tests__/lib/api/versions.test.ts` | +14 |
| FE | `__tests__/components/versions/VersionDiffViewer.test.tsx` | +5 |
| FE | `__tests__/components/versions/VersionCompareSelector.test.tsx` | +7 |
| FE | `__tests__/hooks/work-item/use-comments.test.ts` | +5 (rewritten) |
| FE | `__tests__/hooks/work-item/use-section-comments.test.ts` | +4 |

**Total ≈ 72 new tests.** All green in isolation.

## 7. Pre-existing test-infra debt (NOT this session's fault)

Documented in `tasks/EP-22/tasks.md` already:

- `tests/integration/test_conversation_controller.py`: **12 tests fail on `main` baseline** because PgRateLimiter (EP-12, 10 req/min/IP) exhausts its budget across the suite. All pass in isolation. Verified with `git stash` before and after this session's changes — **this session adds zero new failures**. Root cause: `POST /api/v1/threads` is hit many times in sequence; rate limiter identifier is `ip:127.0.0.1` regardless of test. Fix is test-infra, not feature code — either scope the rate limiter per-test-function or run tests with `--forked`.
- `test_valid_handshake_receives_upstream_frame` (conversation_ws): pre-existing skip/fail on the CSRF path. Same pattern — not fixed here.

**Do not interpret these as regressions.** Always re-run the specific affected test in isolation to confirm.

## 8. Mypy / Ruff state on changed files

- **Mypy strict**: 0 errors on files this session modified (verified with targeted runs).
- **Ruff**: 0 new errors introduced. Pre-existing errors in `app/config/settings.py` (E501 on comment-annotated lines + I001 deferred-import pattern) and `tests/integration/test_conversation_controller.py` (unused `pytest` import) are from main — leave them.

## 9. Parallel agents completed this session (all done, nothing running)

| Agent role | Outcome |
|---|---|
| Track B — sync umbrellas + EP-21 RBP prep | EP-01/02 directories were already deleted (archive); EP-03 umbrella resynced; EP-21 RBP checklist appended |
| Track C — scope EP-03 BE remaining work | Identified WU-3 as highest ROI; clarified line 413 stale |
| db-reviewer — EP-03 RLS research | Found migration 0033 already shipped; unchecked box → ticket rot |
| code-reviewer — EP-22 patches independent review | Flagged 1 Must Fix (REST workspace scoping) + 3 Should Fix (closed or deferred) |
| Explore — EP-12 closure plan | Grouped 16 open boxes; flagged deferred per decision #27 |
| Explore — EP-07 FE diff viewer scope | Confirmed diff viewer ships independently of EP-03 WU-3 |
| frontend-developer — EP-07 Groups 1/3a/3b | 34 tests, 5 new components/types |
| frontend-developer — EP-07 Group 2 | 9 tests, 3 new hooks + API client |

All artifacts persisted in the commits listed in §2. No agent state carries across sessions.

## 10. Recommended next steps (strictly ordered)

1. **User reviews the 10 commits** (`git log main ^origin/main --stat`). Confirm intent to push.
2. **Push** (`git push origin main`) — once user says yes.
3. **Open Dundun cross-repo PR #1** (schema) — coordination item, not a coding task. See `tasks/EP-22/dundun-specifications.md` §4.1 for the exact schema.
4. **EP-07 FE Group 5** — Timeline filters + Timeline tab. Files: `frontend/components/timeline/TimelineFilters.tsx` (new), `/items/[id]/timeline/page.tsx`. Hook `useTimeline` already exists. M effort, no blockers.
5. **EP-12 cursor pagination migration** — admin endpoints still offset-based (`puppet_controller.list_ingest_requests`). S effort per endpoint, low priority (admin, low-traffic).
6. If time permits, **EP-07 FE Group 4** (Comments UI — depends on hooks from this session). L effort; `CommentInput` needs EP-16 upload — start without it.

## 11. Don't-do list (decisions made this session, don't re-open)

- Don't expand scope of `SuggestionService.apply_accepted_batch` with explicit `begin_nested()`. The caller's session commit is already atomic. Add SAVEPOINT only when a multi-phase failure scenario surfaces.
- Don't "fix" the pre-existing rate-limiter test-infra issue under EP-22 scope. Track it separately.
- Don't adopt `require_capabilities` on existing endpoints as a session-wide sweep. Per-epic adoption avoids huge cross-cutting PRs. The gate infrastructure is ready; individual epics pick it up when they need it.
- Don't re-add the Clarificación tab. Spec §9 §US-225 removed it; tests (`__tests__/app/workspace/items/detail-page.test.tsx:181,190,205`) assert its absence.
- Don't hardcode secrets in code. Defaults in `settings.py` are sentinels that raise `ConfigurationError` when `APP_ENV in {production, prod, pre}`.

## 12. Environment snapshot

- Branch: `main`
- Commits ahead of `origin/main`: **10** (this session) + ~246 from prior work = ~256 total unpushed (per `git status` at session start).
- Last hook run: successful commit hook on all 10 commits. No `--no-verify` used.
- Python: 3.13.9
- Test runners: `pytest` (BE), `vitest` (FE).
- No open background processes as of handover.

---

*Generated 2026-04-18 by Tilly. If anything in this doc contradicts what you see in the code, trust the code and update this doc.*
