# EP-21 — Post-MVP Feedback Batch: UX, Bug Fixes & Dev Infra

## Business Need

First manual QA round surfaced six concrete gaps that block productive use of the platform on wide monitors and against real users. Bundled as a single epic because they are all small, share the same release window, and unblock further manual QA on EP-03 (chat), EP-13 (search), EP-18 (MCP) against realistic data.

Source: direct user feedback (2026-04-17, david@aparicioescribano.com).

## Scope — 6 items

| ID | Area | Type | Effort | Layer |
|----|------|------|--------|-------|
| F-1 | Layout widths cap content at `max-w-6xl/7xl` — wastes screen on 1440px+ monitors | Bug / UX | S | Frontend |
| F-2 | Dev seed populates items + teams + tags but leaves **inbox empty** — no notifications to QA | Dev tooling | S | Backend |
| F-3 | Frontend does not refresh after mutations in several flows (verified: `useTeams.addMember` POSTs but never updates local state; suspected siblings) | Bug | M | Frontend |
| F-4 | Errors surface as generic strings — no actionable codes, no field-level mapping, backend detail lost | UX / Observability | M | Backend + Frontend |
| F-5 | No way to **edit work items** from the UI (detail view is read-only; backend `PATCH /work-items/{id}` exists) | Missing feature | M | Frontend |
| F-6 | **Dundun fake HTTP service** to run `docker compose up dundun-fake` and exercise the real conversation flow without blocking on the real Dundun | Dev infra | M | Backend |
| F-7 | Theme toolbar (switcher + red/blue pill + rain toggle) is crammed at the bottom of the sidebar — ugly, out of place. Move to a **user menu dropdown** triggered from the avatar | UX | S | Frontend |
| F-8 | When switching **into** Matrix mode, play a one-shot cascade of phosphor-green glyphs falling top→bottom across the viewport, then settle into the Matrix theme. Distinct from the ambient `RainToggle`. Respects `prefers-reduced-motion` | UX / Delight | S | Frontend |
| F-9 | Tag color field is a plain hex text input (`placeholder="#3b82f6"`). Replace with a real **color picker** (swatch palette + custom hex entry). Same treatment for any other color field that appears in the UI | UX | S | Frontend |
| F-10 | Tags cannot be edited from the UI even though backend exposes `PATCH /tags/{id}` (only `archive` is wired). Add **edit** action (name + color) to the admin tag list | Missing feature | S | Frontend |

## Objectives

- Reclaim horizontal space on wide monitors without breaking mobile/tablet
- Make the dev seed produce a realistic inbox so EP-08 flows are testable end-to-end
- Eliminate the stale-UI class of bugs by enforcing a single mutation→refresh pattern across all hooks
- Turn generic `Error: Request failed` into **error code + human-readable message + offending field** in the UI
- Ship a first-cut edit experience for work items (title, description, priority, state transitions already exist — wire them up)
- Provide a lightweight Dundun fake server (FastAPI, stdlib HTTP, whatever) invokable via docker-compose, reusing the existing in-memory `FakeDundunClient` logic

## Non-Goals

- Full responsive audit across all pages (deferred to EP-12 partial)
- Rewriting the entire API error envelope — additive changes only
- Inline editing / rich-text editor for work item description (only single-shot edit form for MVP)
- Dundun fake ≠ full fidelity — only enough surface to drive conversation + suggestion flows locally
- Internationalization of new error messages — English only in this pass

## User Stories

| ID | Story | Priority | Item |
|---|---|---|---|
| US-230 | As a user on a 1440px+ monitor, items list and admin pages fill a reasonable fraction of the viewport (target: 80% up to `max-w-screen-2xl`) | Must | F-1 |
| US-231 | As a user on mobile/tablet, layouts still respect safe-area padding and do not overflow | Must | F-1 |
| US-232 | As a developer running `seed_sample_data`, I get at least 10 inbox notifications spanning assignment, mention, review-requested, ready-transition events | Must | F-2 |
| US-233 | As a user, after I add a team member / create a tag / add a team, the list updates **without a manual reload** | Must | F-3 |
| US-234 | As a user, when an API call fails, I see `<code>: <message>` (e.g. `VALIDATION_ERROR: Email must be unique`) and, if applicable, the field is highlighted | Must | F-4 |
| US-235 | As a user, I can click "Edit" on a work item and change title, description, priority, and type; save calls `PATCH /work-items/{id}` and the detail view reflects the change | Must | F-5 |
| US-236 | As a developer, `docker compose up dundun-fake` exposes an HTTP server that accepts `POST /messages` and streams WS/SSE responses matching the real Dundun contract | Must | F-6 |
| US-237 | As a developer, I can point the backend at the fake by setting `DUNDUN_BASE_URL=http://dundun-fake:8080` with no other code changes | Must | F-6 |
| US-238 | As a user, I can access theme controls (light/dark/system, red/blue pill, rain toggle) from a dropdown on my avatar, not from a toolbar squatting in the sidebar | Must | F-7 |
| US-239 | As a user, the user menu also exposes `Sign out` and a placeholder `Settings` item, consolidating user-scoped controls in one place | Must | F-7 |
| US-240 | As a user, when I switch into Matrix mode I see a ~1.2s cascade of green glyphs falling across the viewport before the theme settles — it feels like "entering" the Matrix | Should | F-8 |
| US-241 | As a user with `prefers-reduced-motion: reduce`, the cascade is skipped and the theme applies instantly | Must | F-8 |
| US-242 | As a user, switching OUT of Matrix (blue pill) does NOT play the cascade — only the inbound transition is decorated | Must | F-8 |
| US-243 | As an admin creating/editing a tag, I pick the color from a palette of preset swatches with a custom-hex fallback, not by typing `#3b82f6` | Must | F-9 |
| US-244 | As an admin, I can edit an existing tag's name and color from the admin page (pencil icon → modal → save) | Must | F-10 |
| US-245 | As an admin, if I try to save an invalid hex color THEN the form shows a field error (consistent with F-4 envelope) | Must | F-9, F-10 |

## Acceptance Criteria (by item)

### F-1 — Layout widths

- WHEN viewport ≥ 1440px THEN workspace pages (`items`, `items/[id]`, `admin`, `teams`, `inbox`) use `max-w-screen-2xl` (1536px) instead of `max-w-4xl/5xl/6xl/7xl`
- WHEN viewport < 768px THEN layouts keep current mobile padding and scroll behavior
- Explicit opt-out: `new` item form and `inbox` narrow column remain bounded (content is form-shaped, not table-shaped) — document why in `design.md`

### F-2 — Dev seed inbox

- WHEN `python backend/scripts/seed_sample_data.py` runs THEN at least 10 `notifications` rows are inserted for the seed user across `assigned`, `mentioned`, `review_requested`, `state_changed` kinds
- AND re-running the script is idempotent (no duplicates)
- AND at least 3 notifications are `unread`

### F-3 — Frontend refresh after mutation

- WHEN the user adds a team member THEN `useTeams` updates its local state OR re-fetches, and the UI shows the new member without reload
- Same invariant for: tag create/delete, project create/delete, member add to project, work item create, work item state transition
- Audit: every `useX` hook with mutations has a corresponding refresh path — documented in `plan-frontend.md`

### F-4 — Descriptive errors

- Backend: every `HTTPException` / `ValidationError` responds with `{ error: { code, message, field?, details? } }` — code is a stable `SNAKE_CASE` identifier (e.g. `TEAM_MEMBER_ALREADY_EXISTS`, `WORK_ITEM_INVALID_TRANSITION`)
- Frontend: `apiClient` parses the envelope and throws a typed `ApiError(code, message, field?, details?)`
- UI: forms map `field` to the offending input; non-field errors render as a toast with `code: message`
- Existing consumers keep working (backward-compatible envelope — legacy `{ detail: "..." }` still parses)

### F-5 — Edit work item

- WHEN the user clicks "Edit" on `/workspace/[slug]/items/[id]` THEN an edit form opens with prefilled `title`, `description`, `priority`, `type`
- WHEN the user submits THEN `PATCH /api/v1/work-items/{id}` is called and the detail view reflects the new values
- WHEN the user cancels THEN no request is fired and state is unchanged
- State transitions (`inbox → ready`, etc.) already live in the Reviews tab — **not re-implemented here**
- Authorization: only owner or workspace admin can edit; backend already enforces; frontend hides "Edit" otherwise

### F-6 — Dundun fake service

- `infra/dundun-fake/` directory with `Dockerfile`, `main.py`, `requirements.txt` (or reuse backend image + entrypoint)
- Exposes `POST /messages` → echoes back with synthetic `assistant_message` after 300–800ms jittered delay
- Exposes `GET /health`
- Deterministic mode via `FAKE_MODE=deterministic` for E2E; stochastic mode for manual QA
- Added to `docker-compose.dev.yml` alongside Postgres/Redis
- Backend's real `DundunHttpClient` works unchanged against the fake when `DUNDUN_BASE_URL` is set
- README snippet in `infra/dundun-fake/README.md` — 10 lines, not more

### F-7 — Theme controls move to user menu

- WHEN the user clicks the avatar in the sidebar footer THEN a dropdown menu opens
- AND the menu contains: `Theme` subsection (light/dark/system segmented), `Matrix mode` toggle (red pill when off, blue pill when on), `Rain effect` toggle (disabled unless Matrix is active), a divider, `Settings` (disabled placeholder link for now), `Sign out`
- WHEN Matrix mode is active AND the user toggles it off THEN the theme returns to the previously selected non-matrix theme (existing EP-20 behavior preserved)
- WHEN the dropdown is open AND the user presses Esc or clicks outside THEN it closes
- WHEN the viewport is < 768px THEN the dropdown renders as a bottom-sheet (or full-screen modal) to keep tap targets usable
- AND the separate theme toolbar in the sidebar is removed (no duplicate controls)
- AND `aria-label`, `aria-haspopup`, `aria-expanded`, and keyboard navigation (arrow keys, Enter, Esc) are implemented per WAI-ARIA menu pattern
- AND axe-core passes in all three themes with the menu open and closed

### F-8 — Matrix entry cascade

- WHEN the user toggles Matrix mode ON from the user menu
- THEN a full-viewport canvas overlay renders for ~1.2s (configurable via constant)
- AND phosphor-green glyphs (katakana + digits) fall top→bottom in staggered columns (10–15 columns, randomized speed per column)
- AND each glyph fades to black after reaching the bottom OR after its column completes
- AND once the animation ends, the overlay is removed and the Matrix theme is fully applied
- AND `pointer-events: none` during the animation so nothing is blocked
- WHEN `prefers-reduced-motion: reduce` is set THEN the cascade is skipped entirely and the theme applies instantly
- WHEN the user switches OUT of Matrix THEN no cascade plays (inbound-only decoration)
- WHEN the animation is running AND the user triggers another theme change THEN the animation aborts cleanly and the new theme applies

### F-9 — Color picker

- WHEN the user opens the tag create or edit form THEN the color field renders a palette of 12 preset swatches aligned with the design tokens + a "Custom" option
- AND selecting a swatch stores its hex value in the form state
- AND choosing "Custom" opens an inline hex text input (validated `/^#[0-9a-fA-F]{6}$/`)
- AND the current selection is visually indicated (ring around the swatch)
- AND the palette is keyboard-navigable (arrow keys)
- AND the component is reusable — any other color field in the UI uses the same `<ColorPicker>` component

### F-10 — Edit tag

- WHEN the admin views the tag list AND hovers/focuses a tag row THEN an Edit icon appears
- WHEN the admin clicks Edit THEN a modal opens with prefilled `name` and `color` (using the F-9 color picker)
- WHEN the admin submits THEN `PATCH /api/v1/tags/{id}` is called with only changed fields
- AND on 2xx the tag list updates in-place without reload (see F-3)
- AND on validation failure the field error is shown in the modal (see F-4)
- AND authorization: only workspace admin sees the Edit action (backend already enforces)

## Decision needed (F-6 cost-benefit)

User asked whether to build a fake or just launch real Dundun. **Recommendation: build the fake.** Reasons:

- Real Dundun requires network, credentials, rate limits — blocks offline dev and CI
- `FakeDundunClient` logic already exists in `backend/tests/fakes/fake_dundun_client.py` — wrapping it in an HTTP shell is ~2h
- Same fake becomes the E2E fixture and the manual-QA fixture — one artifact, two uses
- Keeps the platform honest about the HTTP contract (if the contract drifts, the fake breaks and we notice)

## Dependencies

- F-1, F-3, F-5 depend on **EP-19** (design system, mutation hook patterns) — already Done
- F-2 depends on **EP-08** (notifications schema) — already Done
- F-4 touches every controller — coordinate with EP-12 error-handling work (partial)
- F-6 depends on **EP-03** (conversation WS) and the existing `FakeDundunClient`

## Open Questions

1. F-1: target max width — `max-w-screen-2xl` (1536) or uncapped with viewport padding? → **Recommendation: 2xl cap + 4rem side padding**
2. F-3: migrate all hooks to TanStack Query in this EP, or patch each hook with manual refresh? → **Recommendation: manual refresh only; TanStack migration is a separate EP**
3. F-4: error-code catalog — new doc or inline in each domain? → **Recommendation: `backend/app/domain/errors/codes.py` central registry**
4. F-5: edit modal or inline-editable fields? → **Recommendation: modal for MVP — inline editing is a UX rabbit hole**
5. F-6: fake language — Python (matches backend) or Node (lighter image)? → **Recommendation: Python, reuse backend deps**
