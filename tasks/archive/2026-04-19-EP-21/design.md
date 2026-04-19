# EP-21 — Design

## Context

First manual-QA round against the deployed MVP surfaced 6 concrete gaps (see `proposal.md`). Nothing here is architectural — this is polish, bug-fixing, and dev-infra. Bundled because they share a release window and unblock the next round of QA on EP-03 (chat), EP-13 (search), EP-18 (MCP).

## Goals

- Fix the three user-facing bugs (F-1 layouts, F-3 stale UI, F-4 opaque errors)
- Ship the one missing feature (F-5 edit items)
- Deliver the two dev-infra pieces (F-2 seed inbox, F-6 Dundun fake) that unlock QA at scale

## Non-Goals

- Global design-system audit (EP-19 done; selective retrofit here)
- Full migration to TanStack Query (logged as follow-up)
- Backend error-middleware rewrite beyond envelope standardisation

## Key Technical Decisions

### D-1 — Layout strategy: `max-w-screen-2xl` + semantic opt-out

**Decision:** raise data-heavy pages to `max-w-screen-2xl` (1536px); keep form-shaped pages at `max-w-4xl`. Introduce two Tailwind utility wrappers `<PageContainer variant="wide" | "narrow">` so the choice is explicit and greppable.

**Alternatives considered:**
- **Uncapped full-viewport** — rejected: 1920px+ text lines become unreadable
- **User-configurable density setting** — rejected: premature, no data yet on preference
- **Per-page ad-hoc `max-w-*`** — rejected: the current mess we are leaving

**Why:** one semantic knob per page, screen real-estate reclaimed, long text still capped via `max-w-prose` inside wide containers.

### D-2 — Mutation refresh: pessimistic local update, no TanStack Query yet

**Decision:** each mutation hook awaits the 2xx response and then either:
1. Updates local state from the response body (preferred — avoids round-trip)
2. Re-fetches the list (fallback when response body lacks the shape)

**Alternatives considered:**
- **TanStack Query migration** — rejected for this EP (scope creep, would touch every hook and every test). Logged as follow-up.
- **Optimistic updates** — rejected: inconsistent UI when backend rejects; complexity not worth it at current scale
- **Polling** — rejected: wasteful; doesn't solve the root cause (hooks forgetting to update)

**Why:** minimal diff per hook, predictable behaviour, keeps the existing test setup untouched. The bug is always the same shape (`POST/PUT/DELETE` without local state update) — fix it in every hook, add a lint rule or audit checklist, move on.

### D-3 — Error envelope: additive + backward-compatible

**Decision:**
- Backend: central registry `backend/app/domain/errors/codes.py` maps domain exceptions to `(code, http_status)`. Global exception middleware serialises to `{ error: { code, message, field?, details? } }`.
- Frontend: `apiClient` parses BOTH new envelope and legacy `{ detail }` shape. Throws typed `ApiError(code, message, field?, details?, status)`.
- Error codes are `SNAKE_CASE` strings (e.g. `WORK_ITEM_INVALID_TRANSITION`). Not an enum, not auto-generated — strings in a Python module, mirrored as TS constants in `frontend/lib/errors/codes.ts`. CI check greps for orphans.

**Alternatives considered:**
- **GraphQL-style `errors[]` array** — rejected: over-engineered for a REST API
- **Full code generation from Python → TS** — rejected: mirror-by-hand is 100 lines; codegen infra is 3 days
- **Keep existing `{ detail }` everywhere** — rejected: field-level UI mapping needs structured errors

**Why:** backward-compatible (no big-bang migration), strict at new write sites, parsed leniently at read sites. The TS mirror is small enough to keep in sync manually.

### D-4 — Work item edit: modal over inline

**Decision:** single modal with prefilled form. Four fields (`title`, `description`, `priority`, `type`). PATCH only changed fields. No optimistic UI. No rich text.

**Alternatives considered:**
- **Inline click-to-edit** — rejected: UX rabbit hole (keyboard nav, focus management, dirty-state per field)
- **Full-page edit view** — rejected: detail view already has the context; modal is sufficient
- **Rich text for description** — rejected: scope; plain textarea works for MVP

**Why:** smallest possible footprint that satisfies the user's request. If inline editing proves valuable, it's a separate future EP.

### D-5 — Seed inbox: reuse notification repo

**Decision:** extend `seed_sample_data.py` to call `NotificationRepository.create()` (same API as production code). Seed 12 notifications spanning 4 kinds, 14 days of `created_at`, 3+ unread. Idempotency key on `(user_id, work_item_id, kind, created_at)` to tolerate re-runs.

**Alternatives considered:**
- **Raw SQL INSERT** — rejected: bypasses the schema source of truth
- **Call notification service (including side-effects like WS broadcast)** — rejected: seed should not trigger realtime push
- **Separate `seed_inbox.py` script** — rejected: one script = one command for the dev

**Why:** one seed command, real repo path, idempotent, deterministic distribution.

### D-9 — Color picker: preset palette + custom hex, reusable component

**Decision:** new `frontend/components/ui/color-picker.tsx` with 12 preset swatches tied to design tokens + a "Custom" radio that reveals a validated hex input. `role="radiogroup"`. Keyboard-navigable. Drop-in replacement — forms import `<ColorPicker value onChange />`.

**Alternatives considered:**
- **Native `<input type="color">`** — rejected: OS-native picker is ugly, inconsistent across browsers, doesn't match the design system, can't theme
- **Port a 3rd-party picker (`react-colorful`, `react-color`)** — rejected for MVP: 40KB+ for a feature that needs 12 presets and a hex field; we don't need HSL/RGB sliders
- **Keep the text input but add live preview swatch** — rejected: doesn't solve the "users don't know hex" problem

**Why:** smallest component that gets the job done, zero new dependencies, themeable via tokens, reusable for any future color field.

### D-10 — Edit tag: frontend-only wiring of an existing endpoint

**Decision:** add an Edit icon per tag row in the admin list, opening the same modal primitive used by F-5 (work item edit). Reuses F-9 `<ColorPicker>`. Calls `PATCH /tags/{id}` with only changed fields.

**Alternatives considered:**
- **Inline editing (click-to-edit tag row)** — rejected: same rationale as F-5; UX rabbit hole
- **Redirect to a dedicated edit page** — rejected: modal is sufficient; admin page is already dense

**Why:** zero backend change, consistent UX with F-5, composes F-9. This is the kind of fix that should have been in EP-15 — we're paying the debt now.

### D-8 — Matrix entry cascade: one-shot canvas, shared drawing primitive with `MatrixRain`

**Decision:** ship a `MatrixEntryCascade` component that mounts when the theme changes from non-matrix → matrix, renders 10–15 columns of phosphor glyphs for ~1.2s, then unmounts. Share the drawing primitive with the existing EP-20 `MatrixRain` (extract `matrix-canvas.ts` utility parameterized by `mode: 'burst' | 'loop'`). Skip entirely on `prefers-reduced-motion`.

**Alternatives considered:**
- **Reuse `MatrixRain` directly with a timer** — rejected: its lifecycle is toggle-based; bolting on one-shot semantics confuses both use cases
- **CSS-only animation** — rejected: can't randomize per-column speed and glyph streams cleanly; canvas is the right tool
- **Video/GIF asset** — rejected: fixed to one resolution, bloated, can't match theme tokens
- **Skip animation, just apply theme** — rejected by the user: this is the signature Matrix moment

**Why:** delight without scope creep. One component, ~100 LOC, shared drawing utility keeps both rain and cascade honest to the same visual language. Strict reduced-motion compliance.

**Hook:** fired from the theme-change handler in `user-menu.tsx` (from F-7), guarded by `previousTheme !== 'matrix' && nextTheme === 'matrix'`.

### D-7 — User menu: consolidate theme + session controls behind the avatar

**Decision:** replace the sidebar theme toolbar with a Radix `DropdownMenu` anchored to the avatar in the sidebar footer. Menu items: identity block, `Theme` segmented group, `Matrix mode` toggle (acts as red/blue pill), `Rain effect` toggle (disabled unless Matrix is on), `Settings` (disabled placeholder), `Sign out`. On mobile, render as a bottom-sheet.

**Alternatives considered:**
- **Keep the toolbar but style it better** — rejected: cosmetic-only, doesn't fix the conceptual incoherence (navigation vs. user controls)
- **Dedicated `/settings` page** — rejected for this EP: too much for controls that are one click deep today; `Settings` row is a placeholder hook for when it's built
- **Top-bar user menu** — rejected: the workspace layout is sidebar-led; no top bar exists and adding one is out of scope

**Why:** single mental model ("anything about *me* lives under my avatar"), matches industry convention (VS Code, Linear, GitHub), keeps sidebar focused on navigation, and leaves a clean hook (`Settings`) for future user-scoped features. Radix primitive gives us a11y + keyboard nav for free.

**Migration:** the `ThemeSwitcher`, `RedPill`, `BluePill`, `RainToggle` components are reused internally by the menu — no throwaway code. Only the *composition* (sidebar toolbar) is removed.

### D-6 — Dundun fake: thin FastAPI app wrapping existing `FakeDundunClient`

**Decision:** new directory `infra/dundun-fake/` with:
- `app.py` — FastAPI app exposing `POST /messages` and `GET /health`
- `Dockerfile` — reuses backend base image (shared Python deps)
- Handler delegates to `FakeDundunClient` (already in `backend/tests/fakes/`) — promoted to `backend/app/infrastructure/fakes/` so both the test suite and the fake service share one source

**Alternatives considered:**
- **Node.js fake** — rejected: smaller image but duplicates the logic in another language
- **WireMock / Mountebank** — rejected: YAML stub files drift from code; we already have the logic in Python
- **Skip the fake, point to real Dundun** — rejected: blocks offline dev, CI, and manual QA (user's original question — my answer stands: build the fake, it's ~2h)

**Why:** DRY (one fake implementation serves unit tests, integration tests, and manual QA), transparent contract (same Python type hints), trivial to extend.

## Security Approach

- **F-1 layouts** — no new attack surface
- **F-2 seed inbox** — guard on `APP_ENV != "dev"` already in place; reuse, never bypass
- **F-3 mutation refresh** — no new surface; pessimistic updates are *more* secure than optimistic (no UI lies about server state)
- **F-4 error envelope** — explicit scrubbing of internal details in production (stack traces, SQL, secrets). Auth errors stay generic to prevent user enumeration.
- **F-5 edit** — authorisation already enforced server-side; frontend hide is UX only. `If-Match`/`updated_at` to prevent lost-update race.
- **F-6 Dundun fake** — dev/e2e compose only; CI rejects the image reference in production compose; fake is stateless (no persistent attack surface).

## Testing Strategy

| Item | Test type | Approach |
|------|-----------|----------|
| F-1 | Playwright visual + a11y | Screenshot diff at 375/768/1024/1440/1920; axe-core at each |
| F-2 | pytest integration | Run seed against ephemeral DB; assert notification count, kinds, unread count, idempotency |
| F-3 | RTL unit per hook | Arrange initial state → act mutation → assert local state updated from response (fake fetch) |
| F-4 | Backend: pytest unit + integration | Assert envelope shape per exception class. Frontend: RTL — assert `ApiError` thrown with correct fields, form shows field error |
| F-5 | RTL component + Playwright E2E | Open modal, edit, save, assert PATCH called with diff + UI reflects |
| F-6 | pytest integration | Boot fake via `docker compose up`; backend `DundunHttpClient` hits it; assert contract |
| F-7 | RTL component + Playwright + axe | Render menu, assert items + roles; keyboard nav; Matrix/Rain interaction; bottom-sheet on mobile viewport; axe-core zero violations in all 3 themes |
| F-8 | RTL + Playwright | Assert cascade mounts only on inbound matrix transition; unmounts after duration; skipped when `prefers-reduced-motion`; abort on re-trigger; no RAF leak |
| F-9 | RTL component + axe | Swatch grid renders; selection; custom hex validation; keyboard nav; zero a11y violations in all 3 themes |
| F-10 | RTL + Playwright | Edit icon admin-only; modal prefilled; PATCH called with diff; refresh without reload; validation error surfaces; non-admin cannot open modal |

All tests RED → GREEN → REFACTOR. No test for the UI width — visual only.

## Rollout

One PR per item is the cleanest story, but they are small enough that 2–3 grouped PRs work too:

- PR-A: F-1 + F-5 + F-7 + F-8 + F-9 + F-10 (frontend, low risk, grouped by review scope; F-9 is a prereq for F-10 so merge in order)
- PR-B: F-3 (frontend, touches many hook files — dedicated PR for reviewability)
- PR-C: F-4 (full-stack, coordinated)
- PR-D: F-2 + F-6 (dev infra)

User picks. Default: PR-A, PR-B, PR-C, PR-D in that order.

## Open Questions

1. **F-4 error codes in TS** — manual mirror or codegen? → Recommendation: manual mirror now; codegen when the registry exceeds ~50 codes
2. **F-5 `If-Match`** — backend currently does not emit ETag. Add it here or defer? → Recommendation: defer (existing code does not have concurrent-edit issue at current scale; EP-17 edit locks cover the main case)
3. **F-6 fake port** — host-bound `localhost:8081` or internal-only? → Recommendation: host-bound, so devs can probe it with `curl` without `docker exec`
