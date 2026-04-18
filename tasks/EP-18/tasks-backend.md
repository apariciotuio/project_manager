# EP-18 · Backend Tasks

Stack: **FastAPI + Python 3.12 + Postgres 16 + Redis 7 + Celery**. MCP server uses the official MCP Python SDK and lives in `apps/mcp-server/`.

Rules (from repo standards):
- **TDD mandatory** — RED → GREEN → REFACTOR. Tests fail first for the right reason.
- **No mocks of internal services** — use fakes / real repos with test DB.
- **Every tool handler has an integration test asserting cross-workspace `-32003`** — non-negotiable.
- **Security by Design** — each capability has a dedicated security task.
- Commits: `<type>(<scope>): <description> Refs: EP-18`
- One logical step per commit.

---

## Capability 1 — Auth & Token Lifecycle

### 1.1 Data model

- [ ] Write migration test (alembic upgrade/downgrade round-trip) for `mcp_tokens` schema
- [ ] Create Alembic migration: `mcp_tokens` table + indexes (`idx_mcp_tokens_ws_user_active`, `idx_mcp_tokens_expires_active`)
- [ ] Add capability constant `MCP_ISSUE = "mcp:issue"` in capability registry; grant to workspace admin role by default
- [ ] Add DB seed: grant `mcp:issue` to existing workspace admins (idempotent)

### 1.2 Domain + Application services (TDD)

- [ ] RED: `test_mcp_token_issue_service_happy_path` — issue returns `{ id, plaintext, expires_at }`
- [ ] RED: `test_issue_rejects_when_not_member_of_workspace`
- [ ] RED: `test_issue_rejects_when_user_already_at_10_tokens`
- [ ] RED: `test_issue_rejects_expires_over_90_days`
- [ ] RED: `test_issue_plaintext_format_matches_regex_and_prefix_mcp_underscore`
- [ ] GREEN: implement `MCPTokenIssueService` — argon2id hash, HMAC lookup key (pepper from secrets), Pydantic model return
- [ ] REFACTOR: extract `TokenSecretGenerator` + `TokenHasher` for reuse in rotate
- [ ] RED: `test_verify_service_returns_actor_and_workspace_on_valid_token`
- [ ] RED: `test_verify_rejects_expired_revoked_wrong_scope`
- [ ] RED: `test_verify_is_constant_time_across_failure_modes` (statistical check, 100 samples, std-dev bound)
- [ ] RED: `test_verify_uses_cache_on_second_call` (count DB queries)
- [ ] RED: `test_verify_cache_invalidated_within_5s_after_revoke`
- [ ] GREEN: implement `MCPTokenVerifyService` with Redis cache, HMAC-then-argon2id chain
- [ ] REFACTOR: extract cache key builder
- [ ] RED: `test_revoke_is_idempotent`
- [ ] RED: `test_revoke_deletes_cache_key`
- [ ] GREEN: implement `MCPTokenRevokeService`
- [ ] RED: `test_rotate_revokes_old_and_issues_new_with_same_name_and_workspace`
- [ ] RED: `test_rotate_emits_two_audit_events_cross_referenced`
- [ ] GREEN: implement `MCPTokenRotateService`
- [ ] RED: `test_last_used_update_is_fire_and_forget_and_drops_if_slow` (inject slow Celery task, assert no request blocking)
- [ ] GREEN: implement async `last_used_at` Celery task

### 1.3 REST admin endpoints (TDD)

- [ ] RED: one integration test per endpoint asserting happy path + auth + authz + validation + idempotency:
  - `POST /api/v1/admin/mcp-tokens`
  - `GET /api/v1/admin/mcp-tokens`
  - `DELETE /api/v1/admin/mcp-tokens/:id`
  - `POST /api/v1/admin/mcp-tokens/:id/rotate`
  - `GET /api/v1/admin/mcp-tokens/mine`
  - `DELETE /api/v1/admin/mcp-tokens/mine/:id`
- [ ] RED: `test_admin_cannot_list_tokens_from_other_workspace`
- [ ] RED: `test_plaintext_only_appears_on_issue_response_never_again`
- [ ] GREEN: implement controllers (thin — parse → service → format)
- [ ] GREEN: add response DTOs; wire OpenAPI

### 1.4 Security tasks

- [ ] Threat review: token theft, offline brute force, timing attack, enumeration, `mcp:issue` abuse — document mitigations in `specs/auth-and-tokens/spec.md#security` (already drafted, verify code matches)
- [ ] Add bearer-token redaction filter to structured-log middleware; unit test covering `Authorization: Bearer ...` and JSON bodies with `plaintext_token` field
- [ ] Pepper management: add `MCP_TOKEN_PEPPER` env var wiring, document rotation procedure in `apps/mcp-server/SECURITY.md`
- [ ] Publish token format regex `^mcp_[A-Za-z0-9_-]{43}$` for secret scanners; add to repo `.secretscanner` config

### 1.5 Observability

- [ ] Emit audit events `mcp_token.issued`, `mcp_token.revoked`, `mcp_token.rotated` with `{ actor_id, target_user_id, token_id, rotated_from?, rotated_to? }`
- [ ] Prometheus counters: `mcp_token_issued_total`, `mcp_token_revoked_total`, `mcp_token_rotated_total`

---

## Capability 2 — MCP Server Bootstrap

### 2.1 Project scaffolding

- [ ] Create `apps/mcp-server/` with `pyproject.toml`, pinned MCP Python SDK version, shared deps on `packages/services/`, `packages/schemas/`, `packages/domain/`
- [ ] Dockerfile (multi-stage, final image < 250 MB compressed)
- [ ] Helm values entry + k8s manifests (Deployment, Service, ServiceAccount, ConfigMap)
- [ ] CI: new `e2e-mcp` job; smoke tests on every PR touching `apps/mcp-server/` or `packages/schemas/`

### 2.2 Core server (TDD)

- [ ] RED: `test_initialize_returns_server_info_and_capabilities`
- [ ] RED: `test_initialize_rejected_without_token`
- [ ] RED: `test_stdio_closes_after_30s_without_initialize`
- [ ] RED: `test_http_single_call_verifies_bearer`
- [ ] RED: `test_sse_upgrade_requires_bearer`
- [ ] GREEN: implement server bootstrap with MCP Python SDK, both transports
- [ ] RED: `test_session_context_is_immutable_for_connection_lifetime`
- [ ] GREEN: implement session context container

### 2.3 Middleware (TDD)

- [ ] RED: `test_auth_middleware_maps_unauthenticated_to_minus32001`
- [ ] RED: `test_auth_middleware_maps_wrong_scope_to_minus32003`
- [ ] GREEN: implement auth middleware calling `MCPTokenVerifyService`
- [ ] RED: `test_rate_limiter_returns_minus32005_with_retry_after_ms`
- [ ] RED: `test_rate_limiter_scopes_keys_per_token_and_per_ip`
- [ ] GREEN: implement rate-limit middleware — reuse EP-12 Redis limiter client
- [ ] RED: `test_error_mapper_covers_every_service_exception_class` (table-driven)
- [ ] RED: `test_error_mapper_never_leaks_stack_trace_in_data`
- [ ] GREEN: implement error mapper
- [ ] RED: `test_audit_emitter_fires_and_forgets` (inject broken queue, assert response still succeeds)
- [ ] RED: `test_audit_params_hash_is_sha256_of_canonical_json`
- [ ] RED: `test_audit_drops_on_overflow_and_increments_metric`
- [ ] GREEN: implement audit emitter with bounded in-memory dropbox (1000 events) + Celery publisher

### 2.4 Discovery

- [ ] RED: `test_tools_list_returns_all_registered_tools_with_schemas`
- [ ] RED: `test_tools_list_is_cached_per_process`
- [ ] RED: `test_deprecated_tool_metadata_includes_replaced_by_and_sunset_at`
- [ ] GREEN: implement tool/resource registry
- [ ] RED: snapshot test `tools_list_snapshot` — CI fails on change without review

### 2.5 Health, metrics, config

- [ ] GET `/mcp/health` — liveness + readiness (Redis + Postgres ping)
- [ ] GET `/metrics` — Prometheus exposition
- [ ] Log sanitization: sanitize client_name/client_version (alphanumeric + `.-_ ` only, max 64 chars); unit test
- [ ] Env config: `MCP_LISTEN_HTTP`, `MCP_STDIO_ENABLED`, `MCP_PER_TOKEN_RPS`, `MCP_PER_IP_RPS`, `MCP_SESSION_IDLE_MINUTES`, `MCP_MAX_SESSIONS_PER_POD`, `MCP_AUDIT_QUEUE_MAX`

### 2.6 Security tasks

- [ ] Threat review: batch bypass, SSE hijack, idle DoS, log injection, stack trace leak, stdio env — document mitigations
- [ ] CORS allowlist from config; test rejection of non-allowlisted origin on `/mcp/sse`
- [ ] Constant-time auth path verification (timing test)

---

## Capability 3 — Read Tools: Work Items & Content

For **every** tool below, the step sequence is identical:

1. RED: unit test validating Pydantic input schema — reject unknown fields, wrong types
2. RED: integration test happy path — calls real service with test DB fixture, asserts response shape
3. RED: **cross-workspace forbidden** test — id in other workspace returns `-32003` (mandatory)
4. RED: authz-edge test — missing capability returns `-32003` or omits fields per spec
5. RED: pagination test where applicable — cursor round-trip, `limit` clamping
6. GREEN: implement tool handler — ≤ 30 lines, parse → service → format
7. REFACTOR: extract shared formatters if repetition emerges

### Tools to implement

- [ ] `user.me`
- [ ] `workitem.get` (+ `include_spec_body: false` variant; + 256 KB truncation test)
- [x] `workitem.search` / `search_work_items` — PoC handler implemented in `apps/mcp_server/tools/search_work_items.py`; wired into `server.py`; 25 unit tests + 8 integration tests (2026-04-18)
- [x] `list_projects` — handler in `apps/mcp_server/tools/list_projects.py`; wired into `server.py` dispatch; 12 unit tests; work_item_count deferred to 0 (no COUNT JOIN in MVP); slug omitted (not in Project domain entity) (2026-04-18)
- [x] `read_work_item` — handler in `apps/mcp_server/tools/read_work_item.py`; wired into `server.py` dispatch; 25 unit tests + 10 integration tests; 2000-char truncation per section with "..." marker; workspace isolation via WorkItemService.get raising WorkItemNotFoundError (2026-04-18)
- [x] `list_work_items` — handler in `apps/mcp_server/tools/list_work_items.py`; stub deleted from `server.py`; wired into dispatch; 20 unit tests; state/type/project_id filters forwarded to WorkItemService.list_cursor; limit capped at 100/default 50; _truncated flag from has_next (2026-04-18)
- [x] `list_sections` — handler in `apps/mcp_server/tools/list_sections.py`; wired into `server.py` dispatch; 19 unit tests; workspace isolation via WorkItemService.get; 200-char content preview; completeness derived from is_required + content presence (2026-04-18)
- [x] `create_work_item_draft` — handler in `apps/mcp_server/tools/create_work_item_draft.py`; wired into `server.py` dispatch; 9 unit tests; title validation 3-200 chars; delegates to DraftService.upsert_pre_creation_draft; returns {id, title, state: "draft", created_at} (2026-04-18)
- [x] `get_work_item_completeness` — handler in `apps/mcp_server/tools/get_work_item_completeness.py`; wired into `server.py` dispatch; 11 unit tests; delegates to CompletenessService.compute; LookupError maps to {error: "not_found"}; returns {overall_score, sections[]} with missing_fields on unfilled dims (2026-04-18)
- [ ] `workitem.children` (direct children only; `has_more_children` flag per child test)
- [ ] `workitem.hierarchy` (ancestors + node + children + roll-up; hidden-ancestor redaction test)
- [ ] `workitem.listByEpic` (flat + grouped; non-epic id rejection test)
- [x] `list_comments` — handler in `apps/mcp_server/tools/list_comments.py`; wired into `server.py` dispatch; 6 unit tests (happy path, resolved flag, empty, section_id filter, cross-workspace isolation, invalid UUID); section_id optional filter; resolved=deleted_at is not None (2026-04-18)
- [ ] `versions.list`
- [ ] `versions.diff` (version-mismatch test; 64 KB body truncation test)
- [x] `list_reviews` — handler in `apps/mcp_server/tools/list_reviews.py`; wired into `server.py` dispatch; 6 unit tests (happy path shape, status string, empty, cross-workspace isolation, include_resolved=false excludes CLOSED/CANCELLED, include_resolved=true returns all, invalid UUID); include_resolved default False (2026-04-18)
- [ ] `validations.list` (override visibility test)
- [ ] `timeline.list` (actor-kind distinction test; redacted-payload test)

### Security tasks

- [ ] Enumeration test: compare timing and bodies of `-32002` vs `-32003` paths across all 12 tools — must be indistinguishable except in the soft-delete safe case
- [ ] Payload DoS test: large spec triggers truncation flag without OOM
- [ ] Cursor tampering test: modified cursor → `INVALID_CURSOR`

---

## Capability 4 — Read Tools: Assistant, Search, Extras

Same per-tool TDD sequence as capability 3.

### Tools to implement

- [ ] `assistant.threads.get` (untrusted-content label in description; proposed-sections filter by readability test)
- [ ] `assistant.threads.workspace`
- [ ] `semantic.search` (Puppet proxy; timeout 3s → `-32010` test; post-filter drops unreadable results test; snippet sanitizer whitelist test)
- [ ] `tags.list` (+ `include_archived`)
- [ ] `tags.workitems` (AND/OR mode; > 20 tags rejection test)
- [ ] `labels.list`
- [ ] `attachments.list` (metadata only; never returns binary test)
- [ ] `attachments.signedUrl` (TTL ≤ 5 min, bearer-bound, per-attachment-scope test)
- [ ] `inbox.list` (priority ordering test per §3.8)
- [ ] `workspace.dashboard` (non-admin sees only `workspace_health`; 30s cache test)
- [ ] `jira.snapshot` (exported vs non-exported shapes; divergence flag test)

### Security tasks

- [ ] Puppet authz drift test: craft upstream response referring to unreadable id; assert dropped before client
- [ ] XSS sanitizer test: malicious HTML in Puppet snippet → escaped except whitelist tags
- [ ] Signed URL replay test: URL issued for token A cannot be redeemed by token B
- [ ] Dashboard omission test: non-admin caller never receives admin blocks

---

## Capability 5 — Resources & Live Subscriptions

### 5.1 Resource providers (TDD)

- [ ] RED: `test_resources_list_returns_four_templates_with_subscribable_flag`
- [ ] RED: `test_read_workitem_resource_returns_same_payload_as_workitem_get`
- [ ] RED: `test_read_epic_tree_depth_capped_at_4_with_has_more_descendants_flag`
- [ ] RED: `test_read_workspace_dashboard_rejects_cross_workspace_id`
- [ ] RED: `test_read_user_inbox_returns_inbox_list_payload`
- [ ] GREEN: implement 4 resource providers

### 5.2 SSE bridge (TDD)

- [ ] RED: `test_bridge_subscribes_to_ep12_pubsub_as_consumer`
- [ ] RED: `test_bridge_filters_events_by_workspace_id` (two workspaces in parallel, assert no cross-delivery)
- [ ] RED: `test_bridge_debounces_burst_of_10_updates_within_500ms_to_one_notification`
- [ ] RED: `test_bridge_reauthorizes_on_every_emit` (revoke permission mid-session, assert unsubscribed notification)
- [ ] RED: `test_bridge_security_relevant_events_bypass_debounce` (force-unlock, ownership change)
- [ ] RED: `test_bridge_lag_p95_under_2s_under_load_fixture`
- [ ] GREEN: implement `sse_bridge` + `debounce` + `authz_gate`
- [ ] REFACTOR: extract event-filter composition

### 5.3 Subscription lifecycle (TDD)

- [ ] RED: `test_subscribe_cap_50_per_session_returns_minus32005`
- [ ] RED: `test_unsubscribe_removes_listener`
- [ ] RED: `test_disconnect_cleans_up_all_subscriptions_within_10s`
- [ ] RED: `test_idle_session_30min_closes`
- [ ] RED: `test_epic_tree_subscription_throttled_to_one_per_10s_when_fanout_exceeds_100_per_min`
- [ ] GREEN: implement subscription manager

### 5.4 Security tasks

- [ ] Workspace cross-contamination integration test (two workspaces, two tokens, parallel subscriptions)
- [ ] Authz revocation mid-session test: subscribe → revoke capability → assert `unsubscribed` within 2s
- [ ] Session exhaustion test: 100 sessions saturate pod → new session rejected with `503`

### 5.5 Observability

- [ ] Metric `mcp_sse_bridge_lag_ms` (histogram)
- [ ] Metric `mcp_subscriptions_active` (gauge)
- [ ] Alert: `mcp_sse_bridge_lag_ms` p95 > 2 s for 5 minutes

---

## Cross-cutting

### Schema drift prevention

- [ ] Shared `packages/schemas/` module — Pydantic models imported by both REST and MCP
- [ ] CI check: any change to a shared schema bumps a `schema_version` constant; reviewer confirms backward compatibility or introduces `v2.<tool>`
- [ ] Snapshot test of `tools/list` — changes require reviewer sign-off

### Load tests (new `load/` in `apps/mcp-server/`)

- [ ] 200 RPS on `workitem.get` — p95 < 150 ms warm
- [ ] 1 k concurrent SSE subscriptions per pod — stable memory < 512 MB
- [ ] Puppet outage simulation — no cascade failure
- [ ] Token revocation latency — ≤ 5 s observed

### Documentation

- [ ] `apps/mcp-server/README.md` — how to run stdio + HTTP locally, auth setup
- [ ] `apps/mcp-server/SECURITY.md` — pepper rotation, token revocation SOP, incident response
- [ ] Auto-generated tool catalog page (login-gated) consuming `tools/list`

### Review gates (before GA)

- [ ] `sw-architect` review on design.md + tasks-backend.md
- [ ] `code-reviewer` pass per capability at merge
- [ ] `db-reviewer` on `mcp_tokens` migration + indexes
- [ ] Security review on capability 1 (auth) and capability 4 (signed URLs)
- [ ] `review-before-push` pre-GA

---

## Effort estimate (ballpark)

| Capability | Estimate |
|---|---|
| 1 — Auth & Tokens | 3 days |
| 2 — Server Bootstrap | 3 days |
| 3 — Read Tools (workitem + content) | 4 days |
| 4 — Read Tools (assistant + search + extras) | 4 days |
| 5 — Resources & Subscriptions | 3 days |
| Cross-cutting (load, docs, reviews) | 2 days |
| **Total** | **~19 days (1 engineer)** |

Parallelizable: capabilities 3 and 4 run in parallel after 2 is merged. Effective calendar time with 2 engineers: ~11 days.
