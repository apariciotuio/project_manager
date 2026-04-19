# EP-18 & EP-19 — Architect Review, Round 2

**Reviewer:** sw-architect · **Date:** 2026-04-14
**Verdict:** Ship-able after the Must-fix list. Foundations are sound; specific concrete leaks to plug before coding.

---

## Must-fix

| # | Where | Finding |
|---|---|---|
| M1 | `EP-18/plan-backend.md §1.3` (Verify flow) + `specs/auth-and-tokens/spec.md` (Verification) | **Per-verify argon2id is a scalability trap disguised as a design.** The cache-hit path needs `token_id`, which requires the DB row first (`get_by_lookup_key`). So the hot path is: HMAC → DB lookup → cache check → argon2id only on miss. Under heavy MCP traffic (agent loops), every verify-miss burns 10–20 ms CPU; 20 RPS/token * many tokens = CPU-bound pods. Add: (a) cache keyed by `lookup_key` (not `token_id`) for the hit path, skipping DB entirely, or (b) a pre-auth HMAC-indexed Redis entry populated on issue. Current design fights itself. |
| M2 | `EP-18/design.md §2` "imports the service layer directly" + `plan-backend.md §0.1` (move DTOs to `packages/schemas/`) | **Process-boundary decision is right; coupling story is wrong.** Two independently deployed processes importing the same `packages/application/*` code means schema + service-signature changes become atomic deploys across REST and MCP. No mention of version skew handling when only one of the two images is rolled. Either (a) commit to lockstep deploys (document it, fail CI on mismatch), or (b) add a service-layer version header and a compat matrix. Right now it's implicit. |
| M3 | `EP-18/specs/resources-subscriptions/spec.md` "Bridge to EP-12 SSE Bus" + `plan-backend.md §5.2` | **Re-authz on every emit does not scale.** 1000 subs/pod × hot resource × burst = 1000 authz calls per event. No caching strategy declared. At 10x usage this becomes the bottleneck and the source of pathological latency on the bridge. Add: short-lived (~5 s) per-(session, uri) authz cache invalidated by capability/membership change events. Same pattern already accepted for token verify — reuse it. |
| M4 | `EP-18/plan-backend.md §4.2` step 6 (Authz re-check) | **Puppet post-filter authz is N+1 in disguise.** "For every Source with a workspace category, resolve `page_id → platform entity id` and call the existing platform read-check." With `top_k=50` and nested comments/sections, that's 50 authz calls synchronously inside the search tool's p95 < 800 ms budget. Needs batch permission check (`can_read_many(actor, entity_ids) -> set[id]`) or the budget is fantasy. |
| M5 | `EP-18/plan-backend.md §2.5` (Audit emitter) + `specs/server-bootstrap/spec.md` (Audit Emission) | **Audit backpressure strategy is "drop oldest + warn"** — which silently destroys forensic evidence under load. Under 10x usage the first signal of a compromise is precisely when the deque overflows. Required: (a) `mcp_audit_queue_drops_total > 0` is an **error-level** alert, not a metric footnote; (b) synchronous structured log line MUST include enough to reconstruct the event (it currently says "always written", verify fields match the async event); (c) consider a local disk spool (bounded, fsync-optional) before in-memory drop. |
| M6 | `EP-18/specs/auth-and-tokens/spec.md` "Verification" AND `plan-backend.md §1.3` | **Cache-hit on revoked tokens is lossy.** Spec: "WHEN a cache hit exists AND `revoked_at` is still NULL in cache payload THEN the cached result is returned." Revoke path DELs the key — OK — but explicit invalidation across multi-pod Redis clusters with replication lag can miss windows. Document the SLO as "up to 5 s + Redis replica lag" and require Redis cache with `readFromPrimary` for this key prefix, or the 5 s SLO is a wish. |
| M7 | `EP-19/specs/shared-components/spec.md` "`PlaintextReveal`" + `EP-18/plan-backend.md §1.4` issue response | **Plaintext crosses a network boundary before reaching `PlaintextReveal`.** The component's no-persistence invariants are useless if the token ships to the browser via a non-`Cache-Control: no-store`, non-private response, or gets captured by any service worker. Plan notes `Cache-Control: no-store` (good) but there is no explicit ban on storing the response through SWR/React-Query caches on the admin UI side. Add: (a) explicit rule in EP-19 that issuance/rotation responses bypass any client-side query cache (use a direct fetch, no caching layer), (b) security test asserts no copy survives in memory after `onClose`. |
| M8 | `EP-18/plan-backend.md §7` feature flags + `EP-19/design.md §3.10` + `extensions.md#EP-19` | **Three flags (`MCP_SERVER_ENABLED`, `MCP_ENABLED_FOR_WORKSPACE`, `DESIGN_SYSTEM_V1`) with no precedence or combination matrix.** What happens when MCP is GA in workspace W but the admin UI is still behind `DESIGN_SYSTEM_V1=false`? Token issuance UX regresses to the old path — fine, but undocumented. Produce a one-page flag matrix: which flag gates which surface, default values per env, rollout sequence. |

---

## Should-fix

| # | Where | Finding |
|---|---|---|
| S1 | `EP-18/design.md §3.5` (Schema SoT) + `plan-backend.md §0.1` | Pydantic-as-single-source is the right call over OpenAPI, but `schema_version` as a single `Final[str]` constant is too coarse — any field change bumps it globally and triggers a snapshot review on unrelated DTOs. Per-DTO versioning (or at minimum per-module) avoids false-positive churn. |
| S2 | `EP-18/specs/resources-subscriptions/spec.md` Epic-tree throttle (1 per 10 s on > 100 changes/min) | Silent 10 s staleness on a "live" resource is a UX footgun for agents polling as ground truth. Emit a coarser keepalive-style `data.throttled=true, next_retry_after_ms` so consumers can plan. |
| S3 | `EP-18/plan-backend.md §5.2` | Bridge runs one Redis pub/sub consumer per pod (note in §9 Open items). At > 20 pods you amplify Redis fanout 20x for the same message. Pre-commit to a SubscriptionManager-in-pod + shared subscriber decision now, not "reconsider later." |
| S4 | `EP-19/specs/tokens-and-theming/spec.md` (Color tokens) + `EP-19/design.md §3.2` | **Parity test is declared but mechanism is vague.** Asserting every semantic key exists in both `:root` and `.dark` needs a concrete AST/CSSOM walker in CI. Without it, "parity enforced" rots on the first urgent PR. Name the tool (`postcss-custom-properties` + a script, or similar) in the plan. |
| S5 | `EP-19/design.md §3.9` + `extensions.md#EP-19` retrofit order (18 epics, rolling) | **Rolling migration while new epic frontend work is also flowing** guarantees that EP-01 (last in the retrofit queue) diverges from EP-18 (first). Either freeze new FE work in unmigrated epics during their retrofit slot, or accept 2x work. Pick and document. |
| S6 | `EP-19/specs/shared-components/spec.md` "`CommandPalette`" + `plan-frontend.md §2.2 CommandPalette` | Registry is lifecycle-scoped per page (good), but there's no story for multi-tab / multi-window. `useCommandPaletteRegistry` + global shortcut means Tab A's commands may fire while Tab B holds focus. Restrict to `document.hasFocus()` or per-tab registry key. Trivial now, expensive later. |
| S7 | `EP-18/specs/read-tools-assistant-search-extras/spec.md` `attachments.signedUrl` + `plan-backend.md §4.3` | Signed URL encodes `token_id`. When that token is rotated (per §1.3 Rotate flow revokes old immediately), outstanding URLs become invalid mid-flight. Either (a) accept and document TTL ≤ 5 min absorbs the risk, or (b) sign against a stable `attachment_id + user_id` pair, not the ephemeral token. |
| S8 | `EP-18/plan-backend.md §1.2` argon2id parameters "t=2, m=32 MiB, p=1" | 32 MiB × concurrent verifies is memory-real. At 100 concurrent verifies that's 3.2 GiB transient. Either cap concurrency via semaphore or drop m to 16 MiB and raise t. Benchmark-in-CI is mentioned; add a memory bound to the benchmark. |
| S9 | `EP-19/specs/copy-tone-i18n/spec.md` + `plan-frontend.md §1.5` custom `icuLite` | Custom ICU subset is fine now, becomes technical debt at locale #3. Document the exit criteria (e.g., ≥ 20 plural strings across 3 domains → switch to `next-intl`), not "when it hurts." |
| S10 | `EP-18/proposal.md` Tool Catalog lists 21 tools, not "≤20" | Cosmetic but it's round-2 — align the number or drop the cap wording. |

---

## Nitpick

| # | Where | Finding |
|---|---|---|
| N1 | `EP-18/design.md §3.10` vs `specs/auth-and-tokens/spec.md` error code table | `-32002 not_found` policy is described in two places with slightly different wording ("soft-deleted within their workspace" vs "caller would have seen the item had it existed"). Pick one sentence, reference it from the other. |
| N2 | `EP-19/plan-frontend.md §1.4` shadcn install list | `combobox` is not an official shadcn component; it's a pattern over `command` + `popover`. Remove to avoid the first engineer hunting. |
| N3 | `EP-18/plan-backend.md §4.2` Puppet category `tuio-docs:*` | Prefix is mentioned but no allowlist source — config file? Env? Declare the location so ops doesn't invent one. |
| N4 | `EP-19/specs/a11y-and-performance/spec.md` Lighthouse 5 pages includes `/admin/mcp-tokens` — depends on EP-18 admin UI existing at the time Phase A/B runs | Phase order needs a note that this check is conditional until EP-18 admin UI lands. |

---

## Topic-by-topic verdicts (short)

- **Process boundary (separate MCP process vs in-REST):** Correct call. Blast radius, scaling, and stdio-vs-ASGI conflict all justify it. Risk is deploy-skew (see M2).
- **Direct import of services vs HTTP-to-self:** Correct. Avoids DTO re-encoding, authz drift, double observability. Enforce the anti-pattern lint (no repository imports in `tools/`).
- **SSE bridge over EP-12 pub/sub:** Topology right (consumer, not peer publisher). Missing: authz-cache (M3), multi-pod fanout pre-commit (S3), backpressure when bridge-lag alert fires. Current plan has lag metric but no reaction.
- **Schema drift prevention (Pydantic SoT):** Robust if discipline holds. `schema_version` too coarse (S1). CODEOWNERS on the tools-list snapshot is the right social enforcement.
- **Feature flags:** Individually coherent, collectively undocumented (M8).
- **shadcn copy-into-repo:** Right trade. Own the code, pay manual bug-sync cost quarterly. Risk accepted and disclosed.
- **Semantic tokens + Tailwind extend:** Right layering. Parity enforcement needs to be executable, not aspirational (S4).
- **EP-19 retrofit via extensions.md:** Rolling is right over big-bang. Missing the freeze-or-double-work decision for in-flight FE work (S5).
- **EP-12 vs EP-19 component boundary:** Clean split as written — EP-12 owns structural primitives, EP-19 owns domain atoms + theming. Don't let EP-19 reach into EP-12 internals; write one ADR that says so.
- **10x breakdowns:** Argon2 verify (M1), Puppet post-filter (M4), SSE authz re-check (M3), audit drops (M5). All four are real; all four have cheap mitigations if addressed pre-code.

---

## Files referenced

- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/proposal.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/specs/auth-and-tokens/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/specs/server-bootstrap/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/specs/read-tools-workitem-content/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/specs/resources-subscriptions/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-18/plan-backend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/proposal.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/design.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/tokens-and-theming/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/shared-components/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/copy-tone-i18n/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/specs/a11y-and-performance/spec.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/EP-19/plan-frontend.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/extensions.md`
- `/home/david/Workspace_Tuio/agents_workspace/project_manager/tasks/consistency_review_round2.md`
