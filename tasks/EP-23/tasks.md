# EP-23 — Tasks

Batch epic. Items appended as manual QA surfaces more feedback. Check proposal.md for scope, acceptance criteria, and open questions.

## Status

**Phase**: Proposal only — specs/design/plans not yet written.

## Progress

- [x] Proposal drafted (2026-04-18)
- [ ] Specs per item
- [ ] `design.md`
- [ ] `plan-frontend.md`
- [ ] Implementation (TDD)
- [ ] `code-reviewer` pass
- [ ] `review-before-push`

## Items

### F-1 — Auth/session gate

- [x] Audit: list every route that currently renders without auth — `/workspace/select` and all `/workspace/[slug]/*` were gated by cookie presence but not JWT expiry (2026-04-18)
- [x] Middleware: add `jwtExp()` decode; redirect expired tokens with `reauth=true`; redirect opaque/non-JWT tokens as unauthenticated — `frontend/middleware.ts` (2026-04-18)
- [x] Layout guard: `WorkspaceLayout` returns `null` while `isLoading` or `!isAuthenticated` — prevents workspace UI flash on client-side navigation — `frontend/app/workspace/[slug]/layout.tsx` (2026-04-18)
- [x] Tests: 10 middleware tests (unauthenticated, valid JWT pass-through, expired JWT reauth redirect, opaque token, workspace picker gate, returnTo encoding) + 2 layout guard tests (loading suppresses render, unauthenticated suppresses render) — all green (2026-04-18)
- [ ] Manual QA: hit `/workspace/<slug>` while logged out — must land on `/login` with zero flash

### F-2 — Dashboard lean

- [ ] Remove existing filler stats from the dashboard page
- [ ] Wire `[+ New item]` CTA
- [ ] Wire "Pending to finish" list (owned by me, non-terminal)
- [ ] Wire "Pending my review/accept" list
- [ ] Wire "Recently created by me" list (last 5)
- [ ] Empty states using `EmptyState` primitive
- [ ] Tests: render each block, empty-state rendering, list capping

### F-3 — A11y / missing titles

- [ ] Sweep pages: `items`, `items/[id]`, `teams`, `admin`, `inbox`, `dashboard`
- [ ] Fix missing `aria-label` / visible text on buttons, icon-buttons, filter chips, section headings, form controls
- [ ] Run axe-core — zero "discernible name" violations
- [ ] Document sweep findings in `design.md`

### F-4 — Sidebar "New item" CTA

- [ ] Add primary CTA to sidebar, above profile block
- [ ] Remove / demote duplicates (e.g., Items list header button)
- [ ] Respect auth/role (hide/disable per rules)
- [ ] Keyboard reachability within first 5 Tab stops
- [ ] Tests: render, keyboard nav, role-based visibility

### F-5 — Inbox full-width

- [x] Swap Inbox container to `max-w-screen-2xl` (2026-04-18: all PageContainer instances changed from variant="narrow" to variant="wide")
- [x] Verify mobile padding / safe-area unchanged (mobile tests pass; px-4 base padding preserved)
- [x] Visual regression check (all existing tests pass; new assertion added verifying max-w-screen-2xl class)

### F-6 — Sidebar IA: Workspace vs You

- [ ] Split sidebar into Workspace zone (top) and You zone (bottom)
- [ ] Place `[+ New item]` CTA between zones
- [ ] Audit: no duplicated controls across zones (sign-out once, theme once, etc.)
- [ ] Workspace switch: Workspace zone re-points to new slug, You zone untouched
- [ ] Validate EP-21 F-7 theme controls still inside user menu (no regression)

### F-7 — Work item detail redesign (chat + template + top navbar)

- [ ] Audit current detail page: list all panels, tabs, badges, actions → decide mapping to new layout (template column vs top navbar tab vs status strip)
- [ ] Auto-collapse main sidebar on detail page; restore on exit
- [ ] Two-column layout: left = chat (reuse EP-03 `SplitView` chat), right = template view
- [ ] Section-scoped top navbar with tabs: Template (default), Comments, Reviews, Timeline, Adjuntos, Spec completeness, Diff, Dependencies, History
- [ ] Status strip inside top navbar: lock badge, completeness pill, item type, assignee
- [ ] Action group (right of top navbar): Save / Edit / Lock / More — consolidate existing header actions
- [ ] Preserve chat state across tab switches (do not unmount chat)
- [ ] Template renderer: use item-type template; explicit "No template" notice if absent
- [ ] Responsive: < 1024px collapses to tabbed Chat | Template with the top navbar still functional
- [ ] A11y: WAI-ARIA Tabs pattern, arrow-key navigation, `role="tabpanel"` + `aria-labelledby`, `<h1>` uses item title
- [ ] Tests: tab switching, chat-state preservation, sidebar collapse/restore, responsive collapse, a11y (axe-core)
- [ ] Manual QA: open multiple item types (epic / story / milestone / task) — template renders correctly per type

## Pending decisions

See `proposal.md#Open Questions`. Resolve before writing `design.md`.
