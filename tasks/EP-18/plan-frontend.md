# EP-18 Frontend Implementation Plan

Blueprint for `develop-frontend`. Layered by component → hook → service → page. Each step cites the spec scenario it satisfies and names the test boundary.

**Stack**: Next.js 14 App Router · TypeScript strict · Tailwind · React Testing Library · MSW for API mocking · Playwright for E2E.

**Design system & UX posture**: EP-18 does **not** decide styling, components, palette, typography or tone. Those belong to **EP-19 (Design System & Frontend Foundations)** and **EP-12 (layout primitives)**. EP-18 consumes what EP-19 ships.

What EP-18 reuses from EP-19 / EP-12 (must exist before this epic ships):

- shadcn/ui + Radix component library installed and customized
- Semantic color tokens (`primary`, `destructive`, `success`, `warning`, etc.) — no raw `bg-blue-500`
- Inter typography + size scale
- `<PlaintextReveal>` component (copy + download + auto-clear) — shared with any future "show once" flow
- `<ConfirmDialog>` with typed-name confirmation variant
- `<StateBadge>`, `<EmptyState>`, `<DataTable>`, `<Sheet>`, `<Toast>` primitives
- `<CommandPalette>` / shortcut cheat sheet
- i18n base in ES-ES tuteo, verbs in infinitive, jerga-plana dictionary
- `useAutoClearPlaintext` hook

What EP-18 owns (MCP-specific):

- Copy dictionary for MCP screens (see §0.3)
- Screens `/admin/mcp-tokens`, `/admin/mcp-tokens/[id]/audit`, `/settings/mcp-tokens`
- Wiring of EP-19's `<PlaintextReveal>` into the issue + rotate flows
- Sparkline + invocation tables for the audit viewer

If a pattern needed here is **not yet** in EP-19, the pattern is promoted to EP-19 first and consumed here — never built locally.

**Scope** (see `tasks-frontend.md` for the high-level task list):
- Item 1 — Gestión de claves (admin) (`/admin/mcp-tokens`)
- Item 2 — Visor de invocaciones (auditoría)
- Item 3 — Mis claves (usuario) (`/settings/mcp-tokens`)

**Legend**
- `[S:<cap>/spec.md#scenarios]` → backend spec scenario (we test the UI obeys the contract)
- `[T:<kind>]` → unit | integration | e2e | a11y | security

All steps follow `RED → GREEN → REFACTOR`.

---

## 0. Pre-flight

### 0.1 Types & API client

- [ ] Create `apps/web/src/types/mcp.ts`
  - `McpTokenDTO` — `{ id, user_id, name, created_at, expires_at, last_used_at?, last_used_ip?, revoked_at?, created_by }`
  - `McpTokenIssueRequest` — `{ user_id, name, expires_in_days? }`
  - `McpTokenIssueResponse` — `{ id, plaintext_token, name, expires_at }`
  - `McpTokenListResponse` — `{ data: McpTokenDTO[], pagination }`
  - `McpInvocationAuditDTO` — `{ id, token_id, tool_or_resource, duration_ms, status, error_code?, client_name?, client_version?, happened_at }`

- [ ] Mirror with zod schemas; snapshot diff in CI against backend-generated JSON schema

- [ ] Create `apps/web/src/api/mcp-tokens.ts`:
  ```ts
  listMcpTokens(params)         // GET /api/v1/admin/mcp-tokens
  listMyMcpTokens(params)       // GET /api/v1/admin/mcp-tokens/mine
  issueMcpToken(body)           // POST /api/v1/admin/mcp-tokens
  revokeMcpToken(id)            // DELETE /api/v1/admin/mcp-tokens/:id
  revokeMyMcpToken(id)          // DELETE /api/v1/admin/mcp-tokens/mine/:id
  rotateMcpToken(id)            // POST /api/v1/admin/mcp-tokens/:id/rotate
  ```

- [ ] Create `apps/web/src/api/mcp-audit.ts`:
  ```ts
  listMcpInvocationsByToken(tokenId, cursor?)
  listMcpInvocationsForWorkspace(filters, cursor?)
  ```

[T:unit]
- `test_client_parses_paginated_response`
- `test_client_handles_401_403_409_errors_mapped_to_typed_exceptions`
- `test_issue_response_plaintext_token_is_not_cached_by_fetch_layer`

### 0.2 Routing skeleton

- [ ] `app/admin/mcp-tokens/page.tsx` — server component, gated by capability `mcp:issue`
- [ ] `app/admin/mcp-tokens/[id]/audit/page.tsx` — per-token audit detail
- [ ] `app/admin/audit/page.tsx` — extend existing page with MCP filter preset
- [ ] `app/settings/mcp-tokens/page.tsx` — self-service

- [ ] Add capability guard middleware: non-admin hitting `/admin/mcp-tokens` → 403 page, preserves link for sharing

[T:integration] `test_unauthorized_user_gets_403_page_not_empty_state`

### 0.3 Copy constants

- [ ] `apps/web/src/i18n/en/mcp-tokens.ts` with all user-facing strings; Spanish mirror stub for future.

i18n keys live under `apps/web/src/i18n/es/mcp.ts` (source of truth) with an EN mirror stub in `apps/web/src/i18n/en/mcp.ts` — **same file basename per locale** (Round-2 review SF-5 fix; previously the plan had `i18n/en/mcp-tokens.ts` vs `i18n/es/mcp.ts` which would cause runtime key-resolution failures).

Key strings (Spanish, source of truth):

- `pageTitleAdmin`: "Claves de acceso para agentes"
- `pageSubtitleAdmin`: "Permiten que herramientas externas (como Claude Code) lean el workspace en nombre de un usuario. Nunca escriben."
- `primaryActionAdmin`: "Crear clave"
- `issueTitle`: "Nueva clave de acceso"
- `issueUserLabel`: "Usuario"
- `issueNameLabel`: "Nombre para identificarla"
- `issueNameHelper`: "Por ejemplo: 'Claude Code en mi portátil'"
- `issueAdvancedToggle`: "Opciones avanzadas"
- `issueExpiryLabel`: "Caduca en"
- `issueSubmit`: "Crear clave"
- `plaintextTitle`: "Copia esta clave ahora"
- `plaintextWarning`: "No la volveremos a mostrar. Cópiala ahora y guárdala en un sitio seguro (como tu gestor de contraseñas). Si la pierdes, crea otra."
- `plaintextCopyButton`: "Copiar al portapapeles"
- `plaintextCopiedFlash`: "Copiado — ya puedes pegarla en tu agente"
- `plaintextDownloadButton`: "Descargar como archivo"
- `plaintextCloseButton`: "Ya la he guardado, cerrar"
- `revokeTitle`: "Revocar esta clave"
- `revokeExplanation`: "La clave dejará de funcionar inmediatamente. Los agentes que la usen verán un error."
- `revokeConfirmPrompt`: "Escribe el nombre de la clave para confirmar:"
- `revokeSubmit`: "Revocar"
- `rotateTitle`: "Rotar esta clave"
- `rotateExplanation`: "La clave actual se revoca al momento y se crea una nueva con el mismo nombre y una caducidad nueva."
- `rotateSubmit`: "Rotar ahora"
- `selfServiceIntro`: "Estas son las claves que dejan que agentes externos lean tu trabajo. Nunca escriben. Revoca cualquiera que no reconozcas."
- `emptyStateTitle`: "Aún no hay claves"
- `emptyStateBody`: "Crea una para que un agente externo pueda leer este workspace."
- `errorHumanized`:
  - `TOKEN_LIMIT_REACHED` → "Este usuario ya tiene el máximo de claves activas (10). Revoca alguna antes de crear otra."
  - `USER_NOT_IN_WORKSPACE` → "Ese usuario no pertenece a este workspace."
  - `generic 5xx` → "Algo ha fallado en el servidor. Vuelve a intentarlo en unos segundos."

---

## 1. Item 1 — Admin Token Management

Spec: `specs/auth-and-tokens/spec.md`. Location: `/admin/mcp-tokens`.

### 1.1 `<McpTokensListPage>` (Server Component)

**Responsibility**: fetch + render the list. Filters in URL query. Server-side auth check.

[T:integration]
- `test_list_shows_tokens_grouped_by_user_with_state_badges` — `[S:#listing]`
- `test_list_filters_by_user_query_param_user_id`
- `test_list_toggles_include_revoked_via_query_param`
- `test_list_shows_empty_state_when_no_tokens`
- `test_list_sorts_by_expires_at_asc_by_default`
- `test_list_orders_revoked_tokens_after_active_when_include_revoked_true`

Implementation:
- Read `searchParams` (`user_id`, `include_revoked`)
- Call `listMcpTokens(...)` server-side
- Pass data to client sub-components

### 1.2 `<McpTokenRow>` (Client Component)

Per-row display: name, user (avatar + display_name), state badge (active / expired / revoked), created, expires (relative + tooltip absolute), last_used (relative + ip on hover), created_by.

Actions (conditional):
- **Revoke** if `revoked_at == null`
- **Rotate** if `revoked_at == null && expires_at > now`
- Disabled with tooltip if token expired

[T:unit]
- `test_row_renders_active_badge_when_not_revoked_and_not_expired`
- `test_row_renders_expired_badge_when_expires_at_past`
- `test_row_renders_revoked_badge_with_timestamp`
- `test_row_hides_rotate_when_revoked`
- `test_row_shows_last_used_relative_with_absolute_in_tooltip`
- `test_row_shows_ip_on_hover_and_hides_when_null`
- `test_row_action_menu_keyboard_accessible` — Tab + Enter + Arrow keys

### 1.3 `<IssueTokenDialog>` (Client Component — critical UX path)

Two-step flow:

**Step A — Form (progressive disclosure)**

Default visible fields (cover the 90% case):
- `user` — combobox with type-ahead over workspace members; shows avatar + display_name; required
- `name` — text field with helper text `issueNameHelper`; required; 1–80 chars; autofocus on dialog open

Collapsed `issueAdvancedToggle` section reveals:
- `expires_in_days` — select 7/14/30/60/90, default **30** pre-selected

Form behavior:
- Primary button `issueSubmit` — enabled as soon as both required fields are filled validly; does **not** gate keystrokes
- On 400 with a known code → inline error under the relevant field using `errorHumanized` dictionary; `role="alert"` with `aria-live="polite"`
- On 5xx → toast with `errorHumanized.generic` and a "Reintentar" action
- Cancel → closes dialog, no network call, form state discarded

[T:unit]
- `test_issue_form_requires_user_and_name`
- `test_issue_form_limits_name_length_to_80`
- `test_issue_form_options_are_7_14_30_60_90` — `[S:#issuance]`
- `test_issue_form_default_expiry_is_30_days`
- `test_issue_form_rejects_non_member_user_with_human_error` — `[S:#issuance]` (`USER_NOT_IN_WORKSPACE`)
- `test_issue_form_shows_limit_reached_error_when_409` — `[S:#issuance]` (`TOKEN_LIMIT_REACHED`)

**Step B — Plaintext reveal** (one-time, friendly)

Consumes `<PlaintextReveal>` from EP-19. Configuration for this use case:

- `title`: `plaintextTitle`
- `body`: `plaintextWarning`
- `value`: the issued token plaintext
- `copyLabel`: `plaintextCopyButton`
- `copiedLabel`: `plaintextCopiedFlash`
- `downloadFilename`: `{tokenName}.token`
- `closeLabel`: `plaintextCloseButton`
- `minInteractionGate: true` — the shared component already enforces: 3 s minimum delay AND user must reveal / copy / download before close
- `autoClearMs: 5 * 60 * 1000`

On close the component emits `onClose(tokenSummary)` with plaintext already purged from its state.

EP-18 does NOT re-implement any of this. Tests here cover **only wiring** (config values passed through, callback handling, integration with issue/rotate mutations). Component-level behavior (gate timing, auto-clear, no-persistence, screen-reader contract per Round-2 L-M4) is tested in EP-19 Storybook + integration tests — **not duplicated here**.

**Round-2 additions** (`tasks/reviews/round_2_specialist_reviews_summary.md` A-M7):
- The `POST /api/v1/admin/mcp-tokens` and `.../rotate` responses MUST be fetched with a direct `fetch()` bypassing React Query / SWR / any service worker cache. The issuance response carries plaintext; it MUST NOT end up in any client-side query cache. Implemented in `api/mcp-tokens.ts` via a `no-cache` branch.
- The response Cache-Control header (`no-store`) is enforced server-side; client test spies on `window.caches` + `performance.memory` asserting no copy survives `onClose`.

[T:unit]
- `test_step_b_shows_plaintext_only_after_reveal_toggle`
- `test_step_b_copy_button_writes_to_clipboard_and_flashes_confirmation`
- `test_step_b_download_creates_txt_file_with_token_value`
- `test_step_b_close_button_disabled_for_3s_and_until_interaction`
- `test_step_b_close_button_enabled_after_copy_click`
- `test_step_b_dialog_close_clears_plaintext_from_component_state` — `[S:#security]`
- `test_step_b_plaintext_auto_clears_after_5_minutes_idle` — `[S:#security]`

[T:security]
- `test_plaintext_never_touches_localStorage_sessionStorage_indexeddb`
- `test_plaintext_never_logged_to_console`
- `test_response_headers_include_cache_control_no_store` (Playwright)

### 1.4 `<RotateTokenButton>` + `<RotateTokenDialog>`

- Opens confirmation: "Rotating will immediately invalidate the current token. A new token will be issued with the same name and a fresh expiry."
- On confirm → `rotateMcpToken(id)` → re-use Step B plaintext reveal with a distinguishing header "Rotated token"

[T:unit]
- `test_rotate_confirmation_explains_old_token_invalidation`
- `test_rotate_success_reuses_plaintext_reveal_component`
- `test_rotate_optimistically_moves_old_token_to_revoked_section`
- `test_rotate_rolls_back_optimistic_update_on_server_error`

### 1.5 `<RevokeTokenButton>` + `<RevokeTokenDialog>`

- Confirmation requires typing the **token name** exactly (mitigates click-through) — submit disabled until match
- On confirm → `revokeMcpToken(id)` → optimistic update in list; rollback on error

[T:unit]
- `test_revoke_confirmation_requires_typed_name_match`
- `test_revoke_confirmation_submit_disabled_until_exact_match`
- `test_revoke_optimistic_row_state_active_to_revoked`
- `test_revoke_rolls_back_on_server_error`
- `test_revoke_is_idempotent_ui_no_error_on_already_revoked` — `[S:#revocation]`

### 1.6 Empty, loading, error states

- [ ] Empty state: `<EmptyState>` with primary CTA "Issue MCP token" opening `<IssueTokenDialog>`
- [ ] Loading skeleton with aria-busy
- [ ] Error boundary: generic "Couldn't load tokens" with retry + error_id for support

---

## 2. Item 2 — Invocation Audit Viewer

Spec: `specs/server-bootstrap/spec.md` (audit event contract).

### 2.1 `<PerTokenAuditPage>` — `/admin/mcp-tokens/[id]/audit`

Layout:
- Header: token name + summary stats (total calls 24h, p95 latency, error %)
- 24h sparkline (RPS over time)
- Tool call breakdown table (tool, count, p95 ms, errors %)
- Recent invocations table (timestamp, tool, duration, status badge, error_code, client_name, client_version)
- Cursor pagination

[T:unit]
- `test_per_token_audit_shows_header_stats`
- `test_per_token_audit_renders_sparkline_from_24h_data`
- `test_per_token_audit_tool_breakdown_sorted_by_count_desc`
- `test_per_token_audit_recent_table_paginates_with_cursor`
- `test_per_token_audit_error_codes_shown_with_text_not_color_only` (a11y)
- `test_per_token_audit_empty_state_when_no_invocations`

### 2.2 Extend `<WorkspaceAuditPage>` with MCP preset

- [ ] Add filter preset "MCP invocations" that sets `kind=mcp.*`
- [ ] Add filter chip for `token_id`
- [ ] Add filter chip for `tool_or_resource`
- [ ] CSV export respects current filter

[T:unit]
- `test_audit_page_mcp_preset_sets_kind_filter`
- `test_audit_page_token_id_chip_filters_correctly`

### 2.3 Security / A11y

- [ ] Tables use `<caption>` + `scope="col"` headers
- [ ] Error code badges include text label (never color-only)
- [ ] `params_hash` display is truncated with copy; never expanded inline (prevent accidental peek)
- [ ] No client-side persistence of audit data beyond current session

[T:a11y] Lighthouse ≥ 95 on both pages.

---

## 3. Item 3 — Self-Service View

Location: `/settings/mcp-tokens`. No capability required.

### 3.1 `<MyTokensPage>` (Server Component)

[T:integration]
- `test_mine_page_shows_only_current_user_tokens`
- `test_mine_page_accessible_without_mcp_issue_capability`
- `test_mine_page_hides_issue_cta_for_non_admin`
- `test_mine_page_shows_issue_cta_for_admin_with_helper_link_to_admin_page`

### 3.2 `<MyTokenRow>` (Client Component)

Differences from admin row:
- No user column (always self)
- Action: **Revoke only** (no rotate — rotation is admin-only for simplicity in MVP)
- Shows `last_used_ip` helping user spot unknown usage

[T:unit]
- `test_my_row_revoke_works_without_mcp_issue_capability`
- `test_my_row_hides_rotate_action`
- `test_my_row_highlights_unfamiliar_ip_with_warning_icon_if_differs_from_current_session_ip`

### 3.3 Mobile responsive

- [ ] Desktop (≥ 768 px): table
- [ ] Mobile: card list, revoke action behind overflow menu
- [ ] Revoke confirmation dialog sized for mobile (full-sheet)

[T:integration] `test_responsive_card_layout_at_375px_viewport`

### 3.4 Intro copy

- [ ] `selfServiceIntro` paragraph at top with link to tool catalog docs (gated behind login)
- [ ] Link to help doc "What is an MCP token?"

---

## 4. Cross-cutting

### 4.1 Accessibility

- [ ] All dialogs: focus trap, ESC to close (when allowed), focus returned on close
- [ ] Plaintext reveal field: `aria-label="MCP token, copy now"`, NOT `type="password"` (screen readers need to announce when revealed)
- [ ] All action buttons have `aria-label` when showing icon only
- [ ] Relative timestamps wrap absolute time in `<time datetime="...">` for screen readers
- [ ] Keyboard: Tab order logical; Enter/Space activate; Arrow keys in menus
- [ ] Contrast AA: state badges use text + color, not color alone

[T:a11y]
- Lighthouse run per page, target ≥ 95
- axe-core automated pass in integration tests
- Manual screen-reader spot-check documented in PR description

### 4.2 Security UX

- [ ] CSP headers on all `/admin/mcp-tokens/*` and `/settings/mcp-tokens` pages: strict, no inline scripts
- [ ] `Cache-Control: no-store` on issuance/rotation responses AND on pages that display plaintext
- [ ] Rate-limit UX: when API returns 429 / `-32005` + `retry_after_ms`, show friendly banner with countdown; disable submit during cooldown
- [ ] Detectable token regex published in `apps/web/public/.well-known/mcp-token-format.json` for client-side scanners (optional nice-to-have)

### 4.3 Playwright E2E

Scenarios (`e2e/mcp-tokens.spec.ts`):
- [ ] `admin_issues_copies_and_dismisses_token` — issues, sees plaintext, copies via clipboard API, confirms, closes, row appears in list
- [ ] `admin_revokes_token_and_backend_rejects_next_call` — revokes UI-side, then a fake MCP call endpoint stub returns -32001
- [ ] `admin_rotates_token_old_revoked_new_plaintext` — sees new token, old marked revoked
- [ ] `non_admin_member_cannot_reach_admin_page` — 403 page shown
- [ ] `user_visits_settings_sees_only_own_tokens` — cross-workspace isolation via token visibility
- [ ] `audit_viewer_paginates_and_filters` — per-token and workspace views
- [ ] `mobile_viewport_revoke_via_card_menu` — at 375 px

### 4.4 Docs

- [ ] `docs/mcp-tokens-admin.md` — admin guide
- [ ] `docs/mcp-tokens-user.md` — end-user guide
- [ ] Help tooltip on list page linking to docs

---

## 5. State management

- **URL as state** — filters, pagination, selected token id — via `searchParams` / `router.push`
- **React Server Components** for initial data fetch on all list pages
- **Client-only state** — dialog open/close, form fields, optimistic updates
- **No global store** — React Query only for mutations + cache invalidation on list after issue/rotate/revoke

### 5.1 Optimistic updates

Only on revoke and rotate (safe, easily reversed). Issue is NOT optimistic (plaintext is authoritative from server).

Pattern:
```ts
const mutation = useMutation({
  mutationFn: revokeMcpToken,
  onMutate: async (id) => {
    await qc.cancelQueries(["mcp-tokens"])
    const prev = qc.getQueryData(["mcp-tokens"])
    qc.setQueryData(["mcp-tokens"], (old) => markRevoked(old, id))
    return { prev }
  },
  onError: (_err, _id, ctx) => qc.setQueryData(["mcp-tokens"], ctx.prev),
  onSettled: () => qc.invalidateQueries(["mcp-tokens"]),
})
```

[T:integration] `test_revoke_rolls_back_on_500_and_shows_error_toast`

---

## 6. File structure

```
apps/web/src/
├── app/
│   ├── admin/
│   │   ├── mcp-tokens/
│   │   │   ├── page.tsx                      # list
│   │   │   └── [id]/audit/page.tsx           # per-token audit
│   │   └── audit/page.tsx                    # extended with MCP preset
│   └── settings/
│       └── mcp-tokens/
│           └── page.tsx                      # self-service
├── components/mcp-tokens/
│   ├── McpTokenRow.tsx
│   ├── IssueTokenDialog.tsx                  # composes EP-19 <PlaintextReveal>
│   ├── RotateTokenButton.tsx
│   ├── RotateTokenDialog.tsx                 # composes EP-19 <PlaintextReveal> (reuse)
│   ├── RevokeTokenButton.tsx
│   ├── RevokeTokenDialog.tsx                 # composes EP-19 <TypedConfirmDialog>
│   ├── EmptyState.tsx                        # composes EP-19 <EmptyStateWithCTA>
│   └── MyTokenRow.tsx
├── components/mcp-audit/
│   ├── PerTokenAuditHeader.tsx
│   ├── Sparkline.tsx                         # simple SVG; no heavy dep; includes sr-only <table> fallback
│   ├── ToolBreakdownTable.tsx
│   └── RecentInvocationsTable.tsx
├── api/
│   ├── mcp-tokens.ts                         # issuance/rotation responses bypass React Query cache (direct fetch)
│   └── mcp-audit.ts
├── types/
│   └── mcp.ts
└── i18n/es/mcp.ts                            # ES tuteo; EN mirror stub in i18n/en/mcp.ts
```

> **Not in this tree** — consumed from EP-19: `<PlaintextReveal>`, `<TypedConfirmDialog>`, `<StateBadge>`, `<CopyButton>`, `<HumanError>`, `<EmptyStateWithCTA>`, `useAutoClearPlaintext`, `useCopyToClipboard`. Per Round-2 review **F-M1** + **F-M3**: EP-18 never re-implements these; any missing pattern is promoted to EP-19 first.

---

## 7. Implementation order

1. **0. Pre-flight** — types, api clients, routing skeleton
2. **Plaintext reveal component** first (shared) with full test suite
3. **Issue dialog** using the reveal component
4. **Revoke flow** (includes confirmation-with-typed-name)
5. **List page** wiring dialogs + row actions
6. **Rotate flow** (reuses reveal component)
7. **Self-service page** (reuses row + revoke)
8. **Audit viewer** (per-token + workspace preset)
9. **Playwright E2E** across all flows
10. **A11y + security pass** — Lighthouse, axe-core, manual SR, DevTools Network inspect
11. **Docs**

### Effort

| Step | Est. |
|---|---|
| 0 Pre-flight | 0.5 d |
| Plaintext reveal | 0.5 d |
| Issue dialog | 0.5 d |
| Revoke flow | 0.3 d |
| List page | 0.3 d |
| Rotate | 0.2 d |
| Self-service | 0.4 d |
| Audit viewer | 1.5 d |
| Playwright | 0.5 d |
| A11y + security pass | 0.3 d |
| **Total** | **~5 d** |

Dependency on backend: capability 1 REST endpoints (`/api/v1/admin/mcp-tokens/*`, `/api/v1/admin/mcp-tokens/mine/*`) must be merged before integration tests run without stubs. Component tests proceed with MSW in parallel.

---

## 8. Open items to confirm with product / design

1. **Expiry options** — is 7/14/30/60/90 days the right list, or do we want a custom picker? Default 30 is confirmed.
2. **Download-as-file** option in plaintext reveal — nice safety net or security foot-gun? Recommend: **include**, labeled clearly, no auto-download.
3. **Unfamiliar-IP warning** in self-service — show or not? Recommend: **show**, small info chip, comparing against current session IP.
4. **Rotate availability for users** — currently admin-only; should user be able to self-rotate their own tokens? Recommend: **yes for MVP**, but only if backend extends `/mine/:id/rotate`.
5. **Copy button** — confirmation message: "Copied" vs "Copied to clipboard — paste it in your agent config." Recommend the second for context.
6. **Auto-clear TTL of displayed plaintext** — 5 minutes default; increase to 10 minutes if user feedback indicates accidental clears?
