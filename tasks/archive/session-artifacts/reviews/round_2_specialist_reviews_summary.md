# Round 2 Specialist Reviews — Consolidated Summary

**Date**: 2026-04-14
**Scope**: EP-18 (MCP Server) + EP-19 (Design System)
**Reviewers**:
- **Architecture** — `sw-architect` — `tasks/reviews/ep18_ep19_architect_review_round2.md`
- **Security** — `code-reviewer` (security focus) — `tasks/reviews/ep18_ep19_security_review_round2.md`
- **Frontend** — `frontend-developer` — `tasks/reviews/ep18_ep19_frontend_review_round2.md`
- **Accessibility** — `code-reviewer` (a11y focus) — `tasks/reviews/ep18_ep19_a11y_review_round2.md`

**Totals**: **24 Must-fix** · **33 Should-fix** · **21 Nitpick** across 4 reviewers.

---

## Must-fix — consolidated (24)

Addressed via addendum blocks in the affected specs (see "Where applied" column). Nothing rewrites specs end-to-end; each change is a targeted clarification or an appended rule that implementation code must follow.

### Architecture (8)

| ID | Finding | Where applied |
|---|---|---|
| A-M1 | Argon2id hot-path cache keyed by `token_id` requires DB lookup first. Cache key should be `lookup_key` (or HMAC-indexed Redis entry populated on issue) to skip DB on cache hit. | `EP-18/specs/auth-and-tokens/spec.md` addendum; `plan-backend.md §1.3` note |
| A-M2 | Two processes importing `packages/application/*` → deploy-skew risk. Commit to lockstep deploys + CI check on image tag mismatch. | `EP-18/design.md §8` addendum (rollout) |
| A-M3 | SSE bridge re-authz on every emit is unbounded CPU. Add short-lived (~5 s) per-(session, uri) authz cache invalidated by capability/membership events. | `EP-18/specs/resources-subscriptions/spec.md` addendum |
| A-M4 | Puppet post-filter is N+1: up to 50 synchronous `can_read` calls per search. Needs batch `can_read_many(actor, entity_ids)`. | `EP-18/plan-backend.md §4.2` addendum |
| A-M5 | Audit backpressure silently drops oldest. Escalate `mcp_audit_queue_drops_total > 0` to error alert; synchronous log line must reconstruct the async event; consider bounded disk spool. | `EP-18/specs/server-bootstrap/spec.md` addendum |
| A-M6 | Cache-hit on revoked tokens has Redis replica-lag window; document SLO as "up to 5 s + replica lag" or force `readFromPrimary` for `mcp:token:*` keys. | `EP-18/specs/auth-and-tokens/spec.md` addendum |
| A-M7 | Plaintext token crosses network: must bypass SWR / React-Query / service-worker caches; security test must assert no memory copy survives `onClose`. | `EP-19/specs/shared-components/spec.md` PlaintextReveal addendum; `EP-18/plan-frontend.md §1.3` note |
| A-M8 | Three feature flags (`MCP_SERVER_ENABLED`, `MCP_ENABLED_FOR_WORKSPACE`, `DESIGN_SYSTEM_V1`) with no precedence. Produce flag matrix. | `tasks/reviews/feature_flag_matrix.md` (new) + `EP-18/design.md §8` reference |

### Security (5)

| ID | Finding | Where applied |
|---|---|---|
| S-M1 | `attachments.signedUrl` ambiguous — plain bearer-re-check or true signed URL? Make **single-use MVP-mandatory**; signature bound to attachment + token + one-shot Redis nonce. | `EP-18/specs/read-tools-assistant-search-extras/spec.md` addendum |
| S-M2 | `params_hash = sha256(canonical_json)` rainbow-tableable on low-entropy inputs (e.g., `workitem.get({id})`). Use HMAC-SHA256 with dedicated audit pepper. | `EP-18/specs/server-bootstrap/spec.md` addendum |
| S-M3 | No audit retention / GDPR erasure / rotation-cadence policy. `last_used_ip: INET` PII unjustified. Define: audit retention 365 days (compliance default), PII minimization on rotation, pseudonymize `last_used_ip` by /24 (IPv4) or /48 (IPv6) unless admin opts in. | `EP-18/specs/auth-and-tokens/spec.md` addendum |
| S-M4 | Puppet category gate uses `startswith` — `tuio-wmp:ws:<ws>:xxx-attacker-owned` bypasses. Use exact-segment match (split on `:` + compare). Document `tuio-docs:*` ingestion ACL (who can write to it). | `EP-18/specs/read-tools-assistant-search-extras/spec.md` addendum + `plan-backend.md §4.2` note |
| S-M5 | SSE sessions verify token only on connect — revocation SLO broken for long-lived subs. Periodic re-verify via cached path (every 60 s or on event). | `EP-18/specs/resources-subscriptions/spec.md` addendum |

### Frontend (5)

| ID | Finding | Where applied |
|---|---|---|
| F-M1 | `EP-18/plan-frontend.md §6` lists local `PlaintextReveal.tsx` in `components/mcp-tokens/` — contradicts preamble "no local definition". Remove; EP-18 §1.3 Step B blocks on EP-19 Phase B.5. | `EP-18/plan-frontend.md §6` edited |
| F-M2 | `CommandPalette` registry keyed by component lifecycle — App Router layouts don't remount on navigation, stale commands accumulate. Key registry by `pathname`. | `EP-19/specs/shared-components/spec.md` CommandPalette addendum; `EP-19/plan-frontend.md §2.2` note |
| F-M3 | EP-18 §1.3 retests `PlaintextReveal` internals (3 s gate, auto-clear). Those belong in EP-19. EP-18 keeps only wiring tests. | `EP-18/plan-frontend.md §1.3` edited |
| F-M4 | Token parity CI check is TypeScript-only — a CSS variable typo passes. Parse `globals.css` directly (AST/regex) and compare keys. | `EP-19/specs/tokens-and-theming/spec.md` addendum |
| F-M5 | `HumanError` shows `correlation_id` to every user — noise for non-technical majority. Gate the disclosure behind a capability or "developer mode" flag. | `EP-19/specs/shared-components/spec.md` HumanError addendum |

### Accessibility (6)

| ID | Finding | Where applied |
|---|---|---|
| L-M1 | Lighthouse sample (5 pages) too narrow. Expand to `{5 canonical + audit + 403} × {light, dark} × {1280, 375}`. | `EP-19/specs/a11y-and-performance/spec.md` addendum |
| L-M2 | axe severity `serious+` too permissive for dialogs. `*ConfirmDialog` + `PlaintextReveal` block on `moderate+`. | `EP-19/specs/a11y-and-performance/spec.md` addendum |
| L-M3 | Focus-return contract has no per-component test entry. Add `test_<dialog>_returns_focus_to_trigger_on_close` for every dialog. | `EP-19/specs/shared-components/spec.md` uniform-API addendum |
| L-M4 | `PlaintextReveal` SR announcement contradictory: `type=text readOnly` + `aria-label="MCP token, copy now"` makes SR read the token on focus. Swap `aria-label` on mask-toggle ("Token oculto" ↔ "Token visible") AND move focus to Copy button on reveal so SR announces "Copy", not plaintext. | `EP-19/specs/shared-components/spec.md` PlaintextReveal addendum |
| L-M5 | `⌘K` global shortcut skipped in form fields (correct for `?` — wrong for `⌘K`). Add `options.allowInFormFields` to `useKeyboardShortcut`. | `EP-19/plan-frontend.md §2.3` note |
| L-M6 | 44×44 touch target only documented, not enforced. Add ESLint rule measuring computed size in Storybook or CSS check. | `EP-19/specs/a11y-and-performance/spec.md` addendum |

---

## Should-fix — summary (33)

Documented per review. **Not applied inline.** Tracked as TODO in `tasks/reviews/round_2_should_fix_backlog.md` (to be created with the first implementation PR). Highlights:

- Arch S1 — per-DTO schema versioning over global `schema_version`
- Arch S2 — epic-tree throttle emits `data.throttled=true` + `next_retry_after_ms`
- Arch S3 — commit to shared SSE subscriber + in-pod fanout now (> 20 pods risk)
- Arch S4 — name the concrete tool for token parity CI check (`postcss-custom-properties` + script)
- Arch S5 — migration/freeze policy: new FE work vs retrofit queue contention
- Sec SF-1 — rotation bypass of 10-token limit
- Sec SF-2 — self-issuance abuse (admin issues for self)
- Sec SF-3 — "untrusted content" label is hope not control on Dundun threads
- Sec SF-4 — `semantic.search` gets its own rate-limit bucket
- Frontend SF-5 — i18n naming mismatch `i18n/en/mcp-tokens.ts` vs `i18n/es/mcp.ts` (align to `i18n/<locale>/mcp.ts`)
- A11y S5 — sparkline fallback: sr-only table or "Ver como tabla" toggle
- A11y S7 — 3 s gate `aria-describedby` live countdown
- A11y S8 — horizontal-scroll assertion at 375 px

Complete list in the four review docs.

---

## Nitpick — summary (21)

Deferred. Full list in the four review docs. Examples:

- Arch N1 — unify `-32002` vs `-32003` policy wording
- Arch N2 — `combobox` not an official shadcn component; document as pattern
- Sec N-series — IP-granularity rate limit, fingerprint on audit, detailed subresource ACL
- Frontend N-series — `CopyButton` aria-live, `i18n/en/*.ts` stub empty-file behavior
- A11y N1..N8 — minor measurement/grouping/live-region tightenings

---

## Action plan

1. ✅ Addendum blocks applied in affected specs (this session).
2. ⏳ **Feature flag matrix** (`tasks/reviews/feature_flag_matrix.md`) — create before implementation.
3. ⏳ **Should-fix backlog** (`tasks/reviews/round_2_should_fix_backlog.md`) — create with first implementation PR.
4. ⏳ Retro-review any addendum that drifts from its source spec at merge time.

**Specialist reviews round 2 status**: **COMPLETED**. No regression vs round 1. Plan is implementation-ready subject to the Should-fix backlog being picked up incrementally.
