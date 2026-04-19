# Security Review — EP-18 + EP-19 (Round 2)

**Date**: 2026-04-14
**Scope**: MCP Server (Read & Query) + Design System specs. Round-1 findings cross-checked for regressions.
**Reviewer**: code-reviewer (security pass)

Round-1 systemic findings (CRIT-1 SSE token-in-query, CRIT-2 workspace scoping, CRIT-4 prompt injection, HIGH-1 SSE channel authz) were **inherited correctly** — EP-18 specs explicitly pin SSE auth to bearer (not query), workspace_id is enforced in the service layer on every tool, and assistant content is labelled as untrusted. No visible regressions. New findings below.

---

## Must Fix

### MF-1. Signed-URL model for attachments is under-specified — replay across sessions
**File**: `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md` §`attachments.list`; table row "Signed URL replay". `tasks/EP-18/plan-backend.md` line 480.

Spec says "scoped to that single attachment id, requiring the same bearer on retrieval". That is **not** a signed URL — that is a bearer re-check dressed up as a signed URL. If the URL is fetched over a different transport (CDN, object-store pre-signed URL, browser `<img>`), the bearer will not travel. If the bearer travels (Authorization header), then the signing provides nothing beyond authz and the attachment endpoint is the real gate. Pick one model and write it down:

- Option A (**recommended**): MCP issues a short-lived, single-use, HMAC-signed URL to the object store, encoding `{attachment_id, token_id, exp, nonce}`. No bearer needed on retrieval. Nonce is consumed in Redis on first use.
- Option B: pure bearer-gated download endpoint; drop the "signed URL" wording entirely.

Current spec is the worst of both — leaves room for an implementation that encodes `token_id` in a query param (see round-1 CRIT-1 — query-param tokens leak to logs). Also: `single-use recommended (post-MVP)` is not acceptable as written — without single-use, a URL captured in a 5-minute window can be replayed from another client (as long as it holds the bearer). Make single-use MVP-mandatory, or acknowledge the replay window in the threat table.

### MF-2. `params_hash` is unsalted sha256 — rainbow-table friendly for low-entropy params
**File**: `tasks/EP-18/specs/server-bootstrap/spec.md` §Audit Emission.

`params_hash = sha256(canonical_json)`. Fine for high-entropy payloads; catastrophic for low-entropy ones. `user.me` has no params → every invocation hashes to the same digest (audit usefulness = 0). `workitem.get({id: UUID})` is enumerable: an attacker with audit-log read can hash every workspace UUID and match against `params_hash` to see which items were accessed. Fix: HMAC with a per-workspace pepper (same secrets-manager pepper family as the token HMAC), or drop the hash and store a size-bounded canonical JSON directly in an encrypted column. Document retention.

### MF-3. Audit retention + token rotation cadence undefined — compliance gap
**Files**: `tasks/EP-18/design.md` §5.5, §8; `tasks/EP-18/specs/auth-and-tokens/spec.md` Non-Functional.

Zero mention of: (a) how long `mcp.invocation` events are retained, (b) GDPR erasure path for `last_used_ip` (PII) on user deletion, (c) mandatory rotation cadence for long-lived tokens (90-day max TTL is permissive). The audit event contains `actor_id`, `token_id`, `ip` — personal data under GDPR. Required: retention policy (recommend 1y hot, 7y cold for DGSFP alignment), erasure procedure, automated rotation reminder at `expires_at - 14d`. Also: `last_used_ip` as `INET` is PII and not justified — hash it or document the legitimate interest.

### MF-4. Puppet post-filter authz-drift gate is single-entity — category-prefix bypass possible
**File**: `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md` §`semantic.search`.

The gate says "category must start with `tuio-wmp:ws:<session.workspace_id>:` OR `tuio-docs:*`". A misconfigured Puppet ingestion that creates a category like `tuio-wmp:ws:<session.workspace_id>:xxx-but-owned-by-attacker` bypasses the prefix check. The prefix match must be **exact segment**, not `startswith`: split on `:`, assert segments `[0]=="tuio-wmp" && [1]=="ws" && [2]==session.workspace_id && [3] IN {"workitem","section","comment"}`. Also: `tuio-docs:*` is treated as trusted global — if any workspace can ingest into `tuio-docs:*` this becomes a cross-tenant leak. Spec must state ingestion ACL: only platform superadmin job may write `tuio-docs:*`.

### MF-5. SSE bearer on connect — no documented idle-token re-verification
**File**: `tasks/EP-18/specs/server-bootstrap/spec.md` §Transport & Handshake; `tasks/EP-18/specs/resources-subscriptions/spec.md` §Authz Re-check.

Resource-read authz is re-checked on every emit (good). But **token validity** (revoked? expired?) is only checked on connect. A long-lived SSE session with a token revoked mid-session keeps receiving notifications until `resources/unsubscribe` because the subscription-level authz re-check calls the application service with a session `actor_id` that was captured at connect. Add: periodic token re-verification (every ≤ 60s) on the SSE loop; on failure, close the session with `-32001`. The 5s cache already exists — use it.

---

## Should Fix

### SF-1. 10-token-per-user-per-workspace limit is trivially bypassable by admin rotation
**File**: `tasks/EP-18/specs/auth-and-tokens/spec.md` §Issuance + §Rotation.

Rotation "revokes old, issues new with fresh `expires_at`". Nothing prevents a malicious admin from creating 10 tokens, rotating all 10 continuously to keep plaintexts flowing to an external party without appearing in the active-count. Add: rotation counts against a weekly ceiling; rotation within < 24 h of issuance triggers alert + extra audit flag `suspicious_fast_rotation`.

### SF-2. `mcp:issue` self-grant not prevented
**File**: `tasks/EP-18/specs/auth-and-tokens/spec.md` §Issuance.

Any admin with `mcp:issue` can mint tokens for themselves. Combined with `user_id must be a member`, an admin can self-issue indefinitely. Not a bug on its own, but no four-eyes or rate limit on self-issuance. Add: `issued_to == issued_by` emits `audit.self_issuance=true`; weekly cap on self-issuance (e.g., 3/week) unless overridden by a second admin.

### SF-3. Dundun thread prompt-injection note only in tool description
**File**: `tasks/EP-18/specs/read-tools-assistant-search-extras/spec.md` §`assistant.threads.get`.

"Tool description labels content as untrusted" is hope, not a control. Downstream agents routinely ignore descriptions. Harden at the data boundary: wrap each message body in a machine-readable envelope `{kind:"untrusted_user_content", body:"..."}` so downstream MCP consumers can filter structurally. Also: scan assistant content for known injection markers (`ignore previous instructions`, system-prompt exfil strings) and set `flagged:true` on the message — non-blocking, audit signal.

### SF-4. Rate-limit sharing with REST may under-limit LLM-adjacent MCP calls
**File**: `tasks/EP-18/specs/server-bootstrap/spec.md` §Rate Limiting.

20 RPS/token is generous for `semantic.search` (Puppet $$ + latency). Round-1 MED-2 required LLM-specific limits on REST — same rule applies: `semantic.search` needs its own bucket (suggest 5 RPS burst 10). Otherwise the MCP surface becomes the LLM-cost loophole around REST limits.

### SF-5. `CommandPalette` cross-workspace — guarantee is in prose, not in architecture
**File**: `tasks/EP-19/specs/shared-components/spec.md` §`CommandPalette`, Security table.

"Registry is scoped to the current session" — depends entirely on every registrant behaving. A single page that registers a global-scope command leaks. Add: registry API requires `{workspaceId}` on every `register()` call; palette filters by current `workspaceId` at render; tests assert a command from workspace A never renders in workspace B. Lint rule to reject `register()` without workspaceId.

### SF-6. `HumanError` disclosure can include `correlation_id` — verify it is not a PII vector
**File**: `tasks/EP-19/specs/shared-components/spec.md` §`HumanError`.

Correlation IDs should be random opaque UUIDs. Spec does not forbid embedding `user_id`, `ip`, or `token_id` in the disclosure. Add: disclosure may render only `{code, correlation_id:uuid}`; any other field requires explicit allowlist.

### SF-7. i18n placeholder escaping claim is untested
**File**: `tasks/EP-19/specs/copy-tone-i18n/spec.md` §Security table.

"Placeholder values are escaped by default; the getter never interpolates HTML" — no test scenario asserts it. Required: test that `t("foo", {x:"<img onerror=…>"})` renders as text, not HTML; test that ICU-plural paths also escape. Also: ensure the tone linter does not itself evaluate translation strings (no `eval`, no `Function()`).

---

## Nitpick

### N-1. Audit fallback log may race with Celery recovery
`tasks/EP-18/specs/server-bootstrap/spec.md` §Audit: synchronous log line + Celery queue → on recovery, de-dup policy undefined. Document "logs are authoritative if queue unavailable; no replay".

### N-2. `mcp_` token prefix conflicts with third-party scanners
Confirm `mcp_` prefix is not already claimed by another vendor's secret-scan regex (GitHub's partner program). Coordinate a namespaced prefix like `tuio_mcp_` if needed.

### N-3. `PlaintextReveal` no-persistence — also assert no `prefetch`/service-worker cache
Spec lists localStorage/sessionStorage/IndexedDB/cookies/URL/console. Add: service-worker caches, `navigator.clipboard` history (Chromium), React DevTools serialisation. Integration test should mount with RTL and snapshot component tree for the plaintext string post-close.

### N-4. `epic://{id}/tree` depth-4 cap is arbitrary
Document the memory/latency basis; ensure payload cap from `workitem.get` (256 KB) also applies to the tree read.

### N-5. `client_name`/`client_version` sanitisation regex
"Alphanumeric + `.-_ ` only, 64 chars" — spec-level. Pin the exact regex in the implementation plan to avoid Unicode homoglyph bypasses (`а` Cyrillic vs `a` Latin).

---

## Summary

| Severity | Count |
|---|---|
| Must Fix | 5 |
| Should Fix | 7 |
| Nitpick | 5 |

**Priority**: MF-4 (Puppet prefix bypass → cross-tenant leak) > MF-1 (signed URL ambiguity) > MF-5 (SSE token revoke lag) > MF-3 (compliance) > MF-2 (audit hash).

Round-1 systemic issues appear closed in EP-18. New findings are MCP-specific surface: signed-URL model, audit hashing, long-lived session token revocation, Puppet category bypass, rotation abuse vectors.
