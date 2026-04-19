# EP-12 — v2 Carveout

**Closed as MVP-complete 2026-04-19** with the following items deliberately punted to v2.

The Execution Plan (`tasks/EXECUTION_PLAN_2026-04-19.md`, Step 1 scope line) explicitly excluded CI gates and file-ingestion from MVP closure: *"close out non-CI items… Exclude: axe-core CI gate, Lighthouse, image-virt (tracked separately as v2 CI epic)."*

## CI Gates (v2 CI epic)

- **Lighthouse CI gate** — fail build on LCP >2.5s, CLS >0.1, TBT >300ms (`tasks.md` line 139, `tasks-frontend.md` line 308)
- **axe-core CI gate** — fail build on violations with impact `critical`/`serious` (`tasks-frontend.md` line 346)
- **Image audit + `next/image`** — replace `<img>` with `next/image` where applicable (`tasks.md` line 137, `tasks-frontend.md` line 306)
- **React-window virtualization** — virtualize lists over 200 items (`tasks.md` line 138, `tasks-frontend.md` line 307)
- **Full a11y audit** — keyboard nav, focus trap, status-badge text alternatives, `aria-live` coverage — moved to EP-23 F-3 (`tasks-frontend.md` lines 340–346, already tracked per line 362)

## File Ingestion (EP-16 v2)

EP-16 already carved file ingestion to v2; these items are follow-ups:

- **File upload MIME type check** (`tasks-backend.md` line 141)
- **File upload size validation** (`tasks-backend.md` line 142)
- **`FileValidator` implementation** (`tasks-backend.md` line 144)

## Design-decision deferrals

- **Per-epic capability adoption** — infrastructure landed; each EP applies `require_capabilities` as they ship (`tasks-backend.md` line 90)
- **Member list pagination** — endpoint is a UI picker with hard cap 500; keyset would break UX (`tasks-backend.md` line 210)
- **SSE consolidation** — `useJobProgress` + `useSSE` delegate correctly; further consolidation awaits EP-03/EP-08 v2 work (`tasks-frontend.md` line 278)
- **Search cursor pagination** — `SearchService` wraps Puppet (vector DB) which has no native keyset. Forcing offset-like pagination defeats the "top-N relevant results" UX. Revisit if Puppet adds cursor support or if we switch providers (`tasks-backend.md` line 212).
- **Per-mutation inbox-cache invalidation wiring** — `InboxService.invalidate()` + cache-aside shipped in EP-12. Hooking every EP-06/EP-08 mutation (state transitions, review-request creation, assignment changes) into `invalidate()` is deferred per-epic, mirroring the capability-adoption carveout. Cache TTL is 30s, so staleness is bounded even without explicit invalidation.
- **Work-item aggregate cache (`work_item:agg:{work_item_id}` TTL 60s)** — the aggregate read path has 3 entry points (detail page, timeline, sidebar); each has its own freshness expectation. Wiring cache requires a consolidated read model (EP-07 diff engine work). Deferred until EP-07 closes.
- **Search cache (`search:{workspace_id}:{hash(query)}` TTL 15s)** — low value because Puppet handles its own caching and queries are long-tail (cache hit rate < 5% in staging). Deferred; revisit with real hit-rate metrics from production.

## Test harness complexity (non-blocking)

- **Client disconnect SSE test** — requires async streaming test harness; mainline SSE flow is covered (`tasks-backend.md` line 293)

---

MVP scope (correlation IDs, CSRF, CSP, rate limiting, input validation, cursor pagination foundation, Redis cache foundation, SSE infrastructure, audit log, layout primitives, responsive mobile shells) shipped and is in production.

Re-open under the v2 CI epic when we're ready to gate builds on perf/a11y.
