# EP-23 — Post-MVP Feedback Batch 2: UI/UX refresh & IA fixes

## Business Need

Second manual QA round (2026-04-18, david@aparicioescribano.com) surfaced a cluster of UX/IA problems that together make the app feel unfinished: protected pages render for unauthenticated users, the dashboard shows noise instead of actionable signal, several controls lack names, core actions (like "New item") are buried, and the sidebar mixes workspace-scoped navigation with global user controls.

All items are frontend-only and share the same release window, so they ship as a single batch — same pattern as EP-21.

This epic is **open-ended**: new items may be appended as manual QA continues. Tasks checklist is source-of-truth.

Source: direct user feedback (2026-04-18).

## Scope (initial — will grow)

| ID | Area | Type | Effort | Layer |
|----|------|------|--------|-------|
| F-1 | Auth/session gate: workspace selector and protected pages render **before** the JWT/session check completes — unauthenticated users can currently pick a workspace | Security / UX bug | S | Frontend (middleware + layout guard) |
| F-2 | Dashboard is noise: collapse to a focused panel — `[New item]` CTA + "pending to finish" + "pending review/accept" + last 5 items I created. Drop filler stats. | UX | M | Frontend |
| F-3 | A11y/clarity: multiple buttons, section headers, and filters ship without visible titles or `aria-label` (audit across pages) | A11y / UX | S | Frontend |
| F-4 | "New item" CTA should live in the sidebar, **above** the profile block, always visible on every workspace page | UX | S | Frontend |
| F-5 | Inbox page does not use full width — align with the rest of the workspace sections (`max-w-screen-2xl` per EP-21 F-1) | UX | XS | Frontend |
| F-6 | Sidebar IA: separate **Workspace** navigation (items, teams, admin, audit — all workspace-scoped) from **You** (profile, theme, sign-out — global). No duplicated controls. | IA / UX | M | Frontend |
| F-7 | Work item detail page is overloaded. Redesign: main sidebar auto-collapses, two-column layout — **left** chat (as today), **right** template-only view (fields rendered per item-type template). Everything else (tabs Comments, Reviews, Timeline, Adjuntos, Lock, Spec completeness, Diff…) moves to a **section-scoped top navbar** with tab-like nav. | UX / Redesign | L | Frontend |

## Workspace vs Global — settled facts (drives F-6)

| Entity | Scope | Implication for the sidebar |
|--------|-------|-----------------------------|
| Teams | Workspace-scoped (`teams.workspace_id NOT NULL`, RLS) | Lives under Workspace section |
| Users | **Global** (auth identity) | User menu in "You" section |
| Workspace memberships | Workspace-scoped (`user_id` + `workspace_id`) | Admin > Members (Workspace section) |
| Audit events | Workspace-scoped with **nullable** `workspace_id` for superadmin/auth events | Workspace audit lives here; superadmin cross-workspace view is out of scope for this EP |
| Routes | All feature routes under `/workspace/[slug]/*` already | IA is correct at domain + routing level — only the presentation needs to reflect it |

## Objectives

- Block any protected page from rendering until the session check resolves (no flash of logged-out UI, no workspace leak)
- Replace the dashboard with a focused panel that answers "what do I need to do next?" in one glance
- Close the a11y gap — every interactive control has an accessible name
- Promote the "New item" CTA to a first-class, always-reachable sidebar primary action
- Make the sidebar's information architecture match the domain: workspace-scoped nav on top, user/global controls at the bottom, no ambiguity
- Bring Inbox width in line with the rest of the app
- Redesign the work item detail page around the **chat + template** dyad, moving everything else to a section-scoped top navbar so the user sees signal (content) and not chrome (tabs, panels, lock badges, etc.)

## Non-Goals

- Full redesign of the dashboard (only the content/density pass listed above)
- New entity types, new filters, or new backend endpoints — **frontend-only EP**
- Superadmin cross-workspace audit view (separate epic when superadmin surface is tackled)
- Internationalization of any new copy beyond existing strings
- Mobile-first redesign — responsive behavior must not regress, but mobile polish is out of scope

## User Stories

| ID | Story | Priority | Item |
|---|---|---|---|
| US-300 | As an unauthenticated user, when I hit any `/workspace/*` URL (including the workspace picker) I am redirected to `/login` **before** any workspace UI renders | Must | F-1 |
| US-301 | As an authenticated user with an expired token, the first protected navigation triggers a refresh-or-redirect flow; I never see stale workspace content | Must | F-1 |
| US-302 | As a user on the dashboard, I see one `[+ New item]` CTA, a list of my items pending to finish, a list of items pending my review/acceptance, and the last 5 items I created — nothing else | Must | F-2 |
| US-303 | As a user, if any of the dashboard lists is empty I see a concise empty state with an actionable CTA (e.g., "No items pending — create one") | Must | F-2 |
| US-304 | As a screen-reader user, every button, icon-button, filter control, and section header on workspace pages has a discernible accessible name | Must | F-3 |
| US-305 | As a keyboard user, I can reach the primary `New item` CTA in the sidebar from any workspace page with a single Tab sequence | Must | F-4 |
| US-306 | As a user, the `New item` CTA in the sidebar is visually anchored above the profile block and persists across navigation | Must | F-4 |
| US-307 | As a user on the Inbox page, the layout uses the same `max-w-screen-2xl` container as Items/Admin; content no longer sits in a narrow column on wide monitors | Must | F-5 |
| US-308 | As a user, the sidebar clearly separates workspace-scoped navigation (Items, Teams, Admin, Audit) from global user controls (profile, theme, sign-out); there are no duplicated controls | Must | F-6 |
| US-309 | As a user, when I switch workspaces the workspace-scoped section swaps to the new slug but my profile/theme/sign-out controls stay untouched | Must | F-6 |
| US-310 | As a user opening a work item, the main sidebar auto-collapses to give the detail page the full viewport width | Must | F-7 |
| US-311 | As a user on a work item, the page shows two columns: chat on the left, the item template on the right — nothing else by default | Must | F-7 |
| US-312 | As a user, the template column renders the fields prescribed by the item's type template (story, epic, milestone, task…) — no generic "description blob" fallback when a template exists | Must | F-7 |
| US-313 | As a user, auxiliary views (Comments, Reviews, Timeline, Adjuntos, Lock info, Spec completeness, Diff, Dependencies, History…) are reachable from a **top navbar** anchored to the detail page, not from stacked panels | Must | F-7 |
| US-314 | As a user, the top navbar indicates the active view and keyboard/focus cycles through it in reading order | Must | F-7 |
| US-315 | As a user, switching views in the top navbar preserves chat state on the left (does not reload the chat) | Must | F-7 |
| US-316 | As a user on a narrow viewport (< 1024px), the two-column layout collapses to tabs (chat / template) and the top navbar remains functional | Must | F-7 |

## Acceptance Criteria (by item)

### F-1 — Auth/session gate

- WHEN any route under `/workspace/*` is requested AND no valid session cookie / JWT is present THEN Next.js middleware (or the root layout server component) redirects to `/login` **before** rendering workspace UI
- AND the workspace selector page is included in the gate (currently reachable without auth)
- AND the check runs on both initial SSR and client-side navigation
- AND on token expiry, the client-side guard surfaces a re-auth prompt or triggers the refresh flow — does not silently render stale data
- Add a single integration test per layer (middleware redirect + layout guard) to prevent regression

### F-2 — Dashboard lean

- The dashboard page renders exactly these blocks (in order):
  1. `[+ New item]` primary CTA
  2. "Pending to finish" — items owned by me not in terminal state
  3. "Pending my review / accept" — items assigned to me for review
  4. "Recently created by me" — last 5 items I created, newest first
- Existing stats widgets are removed from the dashboard (can stay in a future "Analytics" page if needed — out of scope here)
- Each list caps at N items and links to the full filtered list
- Empty states use existing `EmptyState` component from the design system

### F-3 — A11y / missing titles

- Sweep: every `<button>`, icon-only button, filter chip, section heading, and form control on workspace pages has either visible text or `aria-label` / `aria-labelledby`
- axe-core run on `items`, `items/[id]`, `teams`, `admin`, `inbox`, `dashboard` pages produces **zero** "discernible name" violations
- Document the sweep's findings in `design.md` (checklist of the specific controls fixed)

### F-4 — Sidebar "New item" CTA

- WHEN the user is on any workspace page THEN the sidebar shows a primary CTA button `+ New item` above the profile block
- AND the CTA is rendered **once** — any existing duplicate (e.g., in Items list header) becomes secondary or is removed
- AND activating it opens the existing new-item flow (route or modal — whichever is already wired)
- AND the CTA respects auth/role (hidden or disabled for read-only roles, same rules as today)
- AND it is reachable by keyboard within the first 5 Tab stops from the page top

### F-5 — Inbox full-width

- WHEN the viewport ≥ 1024px THEN the Inbox page container matches `max-w-screen-2xl` (same as EP-21 F-1)
- AND mobile padding and safe-area behavior are unchanged
- No other Inbox functionality changes — layout only

### F-6 — Sidebar IA: Workspace vs You

- Sidebar is split into two zones:
  - **Workspace zone** (top): Dashboard, Items, Inbox, Teams, Admin, Audit — links scoped to the current `/workspace/[slug]`
  - **You zone** (bottom): avatar with user menu (profile, theme, sign-out) — global, not workspace-scoped
- The `[+ New item]` CTA (F-4) sits between the two zones, visually separated
- Switching workspaces: Workspace zone links re-point to the new slug; You zone is untouched
- No duplicated control exists across zones (e.g., sign-out only appears in the user menu, not elsewhere)
- Theme toolbar already migrated in EP-21 F-7 — validate no regression

### F-7 — Work item detail redesign (chat + template + top navbar)

- WHEN a user lands on `/workspace/[slug]/items/[id]` THEN the main app sidebar auto-collapses to icon-only (or hides) so the detail page can use the full viewport
- AND the page renders a **two-column layout**:
  - Left: chat panel (current EP-03 `SplitView` chat — unchanged behavior, just repositioned)
  - Right: **template view** — renders the fields defined by the item-type template; no Comments / Reviews / Timeline / Lock / Diff / etc. in the default view
- AND a **section-scoped top navbar** sits above the two columns (below the global header), exposing the auxiliary views as tabs: `Template` (default), `Comments`, `Reviews`, `Timeline`, `Adjuntos`, `Spec completeness`, `Diff`, `Dependencies`, `History` (items conditional to the backend/feature set already shipped)
- WHEN the user switches tabs in the top navbar THEN only the **right column** swaps content; the left chat stays mounted and preserves its state (message history, input draft, scroll position)
- AND the active tab is visually indicated, keyboard-focusable, and supports left/right arrow navigation (WAI-ARIA Tabs pattern)
- AND lock state / who's editing / spec completeness pill move to a **status strip** inside the top navbar (compact badges), not a full panel
- WHEN the viewport is < 1024px THEN the two-column layout collapses to a **tabbed** layout (Chat | Template) with the top navbar still rendered above, exposing the auxiliary views
- AND the auto-collapse of the sidebar is **only** on the detail page — leaving the detail page restores the previous sidebar state
- AND accessibility: the template column's heading uses the item title as `<h1>`; tabs are `role="tab"` inside `role="tablist"`; panels are `role="tabpanel"` with `aria-labelledby`
- AND the template renderer falls back to a clearly labeled "Generic description" block **only** if the item has no type template — for typed items, missing fields render as empty placeholders, not as a free-text blob
- Reuse existing components where possible: the chat panel, the template renderer (EP-04), the tabbed lock/review/comment/timeline components — this is primarily a **layout** change, not a rewrite

## Dependencies

- F-1 — Next.js middleware patterns established in EP-12
- F-2, F-3, F-4, F-5, F-6 — EP-19 design system primitives (Sidebar, Button, EmptyState, UserMenu from EP-21 F-7)
- F-7 — EP-03 (chat `SplitView`), EP-04 (template renderer + spec completeness), EP-07 (Comments + Timeline + Diff), EP-17 (Lock badge). All components already shipped — F-7 is a recomposition, not new logic
- No backend work required — confirms frontend-only scope

## Open Questions

1. F-1: gate in Next.js middleware (runs at the edge, fast) or in the root `layout.tsx` (server component, has richer access)? → **Recommendation: middleware for the redirect + layout for the hydration of the authenticated user — same pattern the app already uses for locale**
2. F-2: the existing dashboard stats — delete outright or move to a future `/workspace/[slug]/analytics` page? → **Recommendation: delete; do not build a parking lot**
3. F-3: bundle axe-core into CI as a gate, or run it ad-hoc during this pass? → **Recommendation: ad-hoc for this EP; CI gate is an EP-12/EP-19 follow-up**
4. F-4: modal vs route for the new-item flow — confirm current choice and keep it; do not re-open the debate here
5. F-6: do we keep `Workspace switcher` at the top of the Workspace zone or in the header? → **Recommendation: keep in header (current), only reorganize sidebar contents**
6. F-7: sidebar auto-collapse — collapse to icon-only (still visible) or hide entirely (full-width detail)? → **Recommendation: icon-only — keeps workspace context reachable in one click**
7. F-7: what about the detail page's **save/edit/delete** actions (currently in the header)? → **Recommendation: move to the right-hand side of the top navbar as a compact action group (Save / Lock / More…)**
8. F-7: `New comment` / `Request review` / `Add attachment` — inside their respective tabs, or a primary action in the status strip? → **Recommendation: inside their tabs — one primary action per tab, no duplicates in the strip**
9. F-7: should the template column support inline editing or stay read-only with an "Edit" button (EP-21 F-5 pattern)? → **Recommendation: reuse EP-21 F-5 modal pattern for MVP; inline editing is a separate EP**
10. F-7: what happens on items with **no** type template (legacy items)? → **Recommendation: render the generic description block with an explicit "No template — using generic view" notice, so it's not silently mistaken for a bug**

## Notes

- This EP is a batch — new items will be appended as QA continues. Update the table at the top and the User Stories / Acceptance Criteria sections together, never one without the other.
- Keep all new copy in English; no i18n rework as part of this EP.
