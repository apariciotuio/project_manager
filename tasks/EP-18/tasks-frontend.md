# EP-18 · Frontend Tasks

Stack: **Next.js App Router + TypeScript strict + Tailwind**. Lives inside the existing admin surface (EP-10). Responsive; mobile target only for self-service token revoke.

Rules:
- **TDD mandatory** — component tests (React Testing Library) RED first
- **Type Safety** — `strict: true`, no `any`
- **A11y** — keyboard navigation, ARIA labels, contrast AA
- **Security by Design** — plaintext token handling is the critical UX path
- Commits: `<type>(<scope>): <description> Refs: EP-18`

---

## Item 1 — Admin Token Management (MCP Tokens Panel)

Location: `/admin/mcp-tokens` (workspace-scoped, gated by capability `mcp:issue`).

### 1.1 API client (TDD)

- [ ] RED: `test_mcp_tokens_client_list_parses_paginated_response`
- [ ] RED: `test_mcp_tokens_client_issue_returns_plaintext_once`
- [ ] RED: `test_mcp_tokens_client_revoke_is_idempotent`
- [ ] RED: `test_mcp_tokens_client_handles_401_403_409` (limit reached, user-not-in-workspace)
- [ ] GREEN: implement `apps/web/src/api/mcpTokens.ts` with typed responses
- [ ] Add zod schemas mirroring backend Pydantic — snapshot diff test against `tools/list` output (CI check)

### 1.2 List page (TDD)

- [ ] RED: `test_list_shows_tokens_grouped_by_user_with_state_badges`
- [ ] RED: `test_list_filters_by_user_via_query_param`
- [ ] RED: `test_list_toggles_include_revoked`
- [ ] RED: `test_list_shows_last_used_relative_and_ip`
- [ ] RED: `test_list_sorts_by_expires_at_asc_by_default`
- [ ] GREEN: implement `app/admin/mcp-tokens/page.tsx` — server component fetching tokens
- [ ] GREEN: `TokenRow` client component with actions (revoke, rotate)
- [ ] Empty state: "No MCP tokens yet" with CTA to issue

### 1.3 Issue dialog (TDD) — critical UX path

- [ ] RED: `test_issue_dialog_requires_user_and_name`
- [ ] RED: `test_issue_dialog_limits_name_length_80`
- [ ] RED: `test_issue_dialog_default_expiry_is_30_days_max_90`
- [ ] RED: `test_issue_dialog_rejects_non_member_user_with_human_error`
- [ ] RED: `test_success_shows_plaintext_once_with_copy_and_warn`
- [ ] RED: `test_success_requires_confirmation_i_saved_it_before_close` (prevents accidental dismiss)
- [ ] RED: `test_dialog_close_after_confirmation_clears_plaintext_from_react_tree` (DOM + memory check)
- [ ] GREEN: implement `IssueTokenDialog` with two-step flow: form → plaintext reveal
- [ ] Warning copy: "This token will NEVER be shown again. Copy it now and store it somewhere safe."
- [ ] Copy button with clipboard API + visual confirmation
- [ ] Download as `.token` file option

### 1.4 Rotate & Revoke flows (TDD)

- [ ] RED: `test_rotate_confirmation_explains_old_token_invalidation`
- [ ] RED: `test_rotate_success_shows_new_plaintext_once_same_security_flow`
- [ ] RED: `test_revoke_requires_confirmation_with_token_name_typed`
- [ ] RED: `test_revoke_updates_list_without_page_reload`
- [ ] GREEN: implement `RotateTokenButton` + `RevokeTokenButton`
- [ ] Optimistic UI with rollback on failure

### 1.5 A11y + security UX

- [ ] Plaintext field uses `input type="text"` (not password) with `readOnly` + `aria-label="MCP token, copy now"` so screen readers announce; but masked by default with reveal toggle
- [ ] Plaintext auto-clears from state 5 minutes after dialog open (defensive)
- [ ] `noindex`, `no-cache`, `Cache-Control: no-store` headers on token-issuance endpoints
- [ ] Keyboard trap inside confirmation modal; focus returned on close
- [ ] Lighthouse a11y ≥ 95 on list page

---

## Item 2 — Invocation Audit Viewer

Location: `/admin/mcp-tokens/:id/audit` and `/admin/audit?filter=mcp`.

### 2.1 API + data (TDD)

- [ ] RED: `test_audit_client_paginates_cursor_and_rejects_tampered_cursor`
- [ ] RED: `test_audit_client_filters_by_token_id_and_tool`
- [ ] GREEN: implement `apps/web/src/api/audit.ts` (extend existing if present)

### 2.2 Per-token audit view (TDD)

- [ ] RED: `test_per_token_audit_shows_tool_duration_status_error_client`
- [ ] RED: `test_per_token_audit_shows_sparkline_of_last_24h_rps`
- [ ] RED: `test_per_token_audit_shows_error_code_breakdown`
- [ ] RED: `test_per_token_audit_shows_top_tools_called_count`
- [ ] GREEN: implement `app/admin/mcp-tokens/[id]/audit/page.tsx`
- [ ] Empty state for tokens with no invocations yet

### 2.3 Workspace-wide MCP audit filter (TDD)

- [ ] RED: `test_audit_page_has_mcp_filter_preset_in_filters_list`
- [ ] RED: `test_filter_by_kind_mcp_dot_prefix_returns_only_mcp_events`
- [ ] GREEN: extend existing `/admin/audit` page with MCP preset + `kind LIKE 'mcp.%'` filter
- [ ] Export to CSV (reuse existing mechanism)

### 2.4 A11y

- [ ] Table uses `<caption>` + `scope="col"` headers
- [ ] Error-code badges include text label, not color-only

---

## Item 3 — Self-Service Token View

Location: `/settings/mcp-tokens` (no capability required; authenticated user only).

### 3.1 List & revoke own tokens (TDD)

- [ ] RED: `test_mine_list_shows_only_own_tokens_even_across_workspaces_via_membership`
- [ ] RED: `test_mine_revoke_works_without_mcp_issue_capability`
- [ ] RED: `test_mine_cannot_issue_only_admin_can` (UI hides issue CTA; endpoint also rejects)
- [ ] GREEN: implement `app/settings/mcp-tokens/page.tsx`

### 3.2 Mobile

- [ ] Responsive card layout for the list on mobile
- [ ] Revoke action accessible via swipe or menu; confirmation dialog reused

### 3.3 Copy explaining scope

- [ ] Short intro: "MCP tokens let external agents (like Claude Code) read your work items on your behalf. They never allow writes. Revoke any token you don't recognize."
- [ ] Link to documentation page (auto-generated tool catalog) gated behind login

---

## Cross-cutting (Frontend)

### Integration tests (Playwright)

- [ ] E2E: admin issues token → copies plaintext → dismisses dialog → token appears in list with `revoked_at: null`
- [ ] E2E: admin revokes token → list updates → backend rejects on next call (verified via API stub)
- [ ] E2E: admin rotates token → new plaintext shown → old token revoked in list
- [ ] E2E: non-admin member navigates to `/admin/mcp-tokens` → receives 403 page
- [ ] E2E: user visits `/settings/mcp-tokens` → sees own tokens only

### Security review

- [ ] Manual pen-test checklist on token-issuance flow: plaintext in DevTools Network tab → expected, but must not appear in `localStorage`/`sessionStorage`/IndexedDB
- [ ] CSP headers on `/admin/mcp-tokens/*` — strict, no inline scripts
- [ ] Rate-limit UX: if backend returns 429/`-32005`, show friendly banner with retry-after countdown

### Docs

- [ ] Short user guide `docs/mcp-tokens-admin.md` embedded as help tooltip on the page

---

## Effort estimate

| Item | Estimate |
|---|---|
| 1 — Admin Token Management | 2.5 days |
| 2 — Invocation Audit Viewer | 1.5 days |
| 3 — Self-Service | 0.5 day |
| Playwright + Docs | 0.5 day |
| **Total** | **~5 days (1 engineer)** |

Dependency: waits on Backend capability 1 REST endpoints.
