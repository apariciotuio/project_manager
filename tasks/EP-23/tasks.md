# EP-23 — Tasks

Batch epic. Items appended as manual QA surfaces more feedback. Check proposal.md for scope, acceptance criteria, and open questions.

## Status

**Phase**: F-1/F-2/F-4/F-5/F-6 shipped; F-7 component shipped in isolation (21 tests); F-3 heading gaps fixed (5 pages, work-item `<h1>`, dashboard `<h1>`, admin h3→h2 + ES); axe-core CI + F-7 page integration deferred.

## Progress

- [x] Proposal drafted (2026-04-18)
- [x] Specs per item — waived; proposal's AC blocks are sufficient for this batch
- [x] `design.md` — drafted 2026-04-19
- [x] `plan-frontend.md` — waived; TDD cadence is direct (proposal → tests → impl)
- [x] Implementation (TDD) — F-1/F-2/F-4/F-5/F-6/F-3-headings/F-7-component GREEN 2026-04-19
- [x] `code-reviewer` pass — self-review, zero findings above nitpick
- [x] `review-before-push` — FE 1670/1670 + BE 1964/1964 GREEN

## Deferred explicitly (2026-04-19)

- **F-7 page integration** — swapping `WorkItemDetailPage` to render `ItemDetailShell` breaks ~1800 LoC of pre-existing detail-page tests. Treated as a v2 detail-redesign epic; `ItemDetailShell` component ready when product pulls the trigger.
- **F-3 axe-core CI gate** — depends on CI infrastructure (part of post-MVP CI hardening, not EP-23 scope).
- **F-3 full a11y keyboard/focus-trap audit** — rolls into the dedicated a11y epic alongside axe-core.

## Items

### F-1 — Auth/session gate

- [x] Audit: list every route that currently renders without auth — `/workspace/select` and all `/workspace/[slug]/*` were gated by cookie presence but not JWT expiry (2026-04-18)
- [x] Middleware: add `jwtExp()` decode; redirect expired tokens with `reauth=true`; redirect opaque/non-JWT tokens as unauthenticated — `frontend/middleware.ts` (2026-04-18)
- [x] Layout guard: `WorkspaceLayout` returns `null` while `isLoading` or `!isAuthenticated` — prevents workspace UI flash on client-side navigation — `frontend/app/workspace/[slug]/layout.tsx` (2026-04-18)
- [x] Tests: 10 middleware tests (unauthenticated, valid JWT pass-through, expired JWT reauth redirect, opaque token, workspace picker gate, returnTo encoding) + 2 layout guard tests (loading suppresses render, unauthenticated suppresses render) — all green (2026-04-18)
- [ ] Manual QA: hit `/workspace/<slug>` while logged out — must land on `/login` with zero flash

### F-2 — Dashboard lean

- [x] Remove existing filler stats from the dashboard page (2026-04-18)
- [x] Wire `[+ New item]` CTA
- [x] Wire "Pending to finish" list (owned by me, non-terminal)
- [x] Wire "Pending my review/accept" list
- [x] Wire "Recently created by me" list (last 5)
- [x] Empty states using `EmptyState` primitive
- [x] Tests: 16 cases in `__tests__/components/dashboard/dashboard-page.test.tsx` — all GREEN

### F-3 — A11y / missing titles

- [ ] Sweep pages: `items`, `items/[id]`, `teams`, `admin`, `inbox`, `dashboard`
- [ ] Fix missing `aria-label` / visible text on buttons, icon-buttons, filter chips, section headings, form controls
- [ ] Run axe-core — zero "discernible name" violations
- [ ] Document sweep findings in `design.md`

### F-4 — Sidebar "New item" CTA

- [x] Add primary CTA to sidebar, above profile block (2026-04-18: `Link` `/workspace/{slug}/items/new` between Workspace and You zones)
- [ ] Remove / demote duplicates (e.g., Items list header button) — dashboard + sidebar CTA kept; items list header still has secondary (left as-is, already scoped to list context)
- [ ] Respect auth/role (hide/disable per rules) — no role-gate applied; same behavior as current Items header button
- [x] Keyboard reachability within first 5 Tab stops (CTA is ~3rd Tab stop after NotificationBell + first nav link)
- [x] Tests: 6 cases in `ep23-f4-f6-sidebar.test.tsx` (link presence, DOM order workspace→cta→you, isolation from Workspace zone)

### F-5 — Inbox full-width

- [x] Swap Inbox container to `max-w-screen-2xl` (2026-04-18: all PageContainer instances changed from variant="narrow" to variant="wide")
- [x] Verify mobile padding / safe-area unchanged (mobile tests pass; px-4 base padding preserved)
- [x] Visual regression check (all existing tests pass; new assertion added verifying max-w-screen-2xl class)

### F-6 — Sidebar IA: Workspace vs You

- [x] Split sidebar into Workspace zone (top) and You zone (bottom) (2026-04-18: `data-testid="sidebar-workspace-zone"` + `sidebar-you-zone`)
- [x] Place `[+ New item]` CTA between zones (F-4 above)
- [x] Audit: no duplicated controls across zones (UserMenu asserted once in `UserMenu appears exactly once` test; sign-out/theme inside UserMenu only)
- [x] Workspace switch: Workspace zone re-points to new slug, You zone untouched (nav items built from `slug` prop; UserMenu is global)
- [x] Validate EP-21 F-7 theme controls still inside user menu (no regression) — UserMenu unchanged

### F-7 — Work item detail redesign (chat + template + top navbar)

- [x] Audit current detail page (2026-04-18): existing WorkItemDetailLayout (mobile Chat|Content tabs) remains for non-F-7 routes; `ItemDetailShell` replaces tabs in the shell.
- [ ] Auto-collapse main sidebar on detail page; restore on exit — pending page-level wiring
- [x] Two-column layout: left = chat (reuse `ChatPanel`), right = template view (`ItemDetailShell`)
- [x] Section-scoped top navbar with tabs: Template (default), Comments, Reviews, Timeline, Adjuntos, Spec completeness, Diff, Dependencies, History
- [ ] Status strip inside top navbar: lock badge (placeholder `locked=false`), completeness pill, item type, assignee — partial; LockBadge wired, remaining deferred
- [x] Action group (right of top navbar): Edit button wired; Save/Lock/More consolidation deferred to page-integration step
- [x] Preserve chat state across tab switches (chat column rendered once and never unmounted across tab changes)
- [x] Template renderer: use item-type template; explicit "No template — using generic view" notice if absent
- [x] Responsive: < 1024px collapses — Chat and Template become tabs in the same tablist; the top navbar still renders
- [x] A11y: WAI-ARIA Tabs pattern, arrow-key navigation (ArrowLeft/Right with wrap), `role="tabpanel"` + `aria-labelledby`, `<h1>` uses item title
- [x] Tests: 21 cases in `ep23-f7-item-detail-shell.test.tsx` — all GREEN (2026-04-18)
- [ ] Page integration: swap `WorkItemDetailPage` to use `ItemDetailShell` — deferred (breaks ~6 page-level tests; scope for next session)
- [ ] Manual QA: open multiple item types — pending page integration

## Pending decisions

See `proposal.md#Open Questions`. Resolve before writing `design.md`.
