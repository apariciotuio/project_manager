# EP-23 — Design Notes

> Batch epic — items ship independently. This doc records the non-obvious design decisions taken while shipping F-1..F-7.

## F-1 — Auth/session gate

- **Where**: Next.js middleware + `WorkspaceLayout` server component.
- **Pattern**: two-layer guard.
  - Middleware decodes the JWT `exp` claim without verifying the signature (token stays server-authoritative; this is a client-side expiry pre-check only). Expired tokens redirect to `/login?reauth=true&returnTo=...`. Missing tokens redirect to `/login?returnTo=...`.
  - `WorkspaceLayout` returns `null` while `useAuth()` reports `isLoading || !isAuthenticated`. Prevents the client-side navigation flash.
- **Why middleware + layout**: middleware is fast (edge, no bundle) but can't access `AuthProvider` state; layout can, but only after hydration. Using both closes the gap.

## F-2 — Dashboard lean

- **Deleted**: `DashboardSummary`, `StateDistributionChart`, `TypeDistributionChart`, `RecentActivityFeed`, `useDashboard` hook. Filler stats are gone.
- **Added**: four sections — `[+ New item]` CTA, Pending to finish, Pending my review, Recently created by me. Each section caps at 5, links to its full filtered list, renders `EmptyState` when empty.
- **Data**: reuses `useWorkItems` with client-side filter per section. No new endpoint.

## F-3 — A11y / missing titles

Deferred for this session. Needs axe-core integration (decision: "ad-hoc for this EP, CI gate as EP-12/EP-19 follow-up"). Tracked in `tasks.md#F-3`.

## F-4 + F-6 — Sidebar CTA + IA

- **Single `WorkspaceSidebar` component** renders three zones via `data-testid="sidebar-workspace-zone"`, `sidebar-new-item-cta`, `sidebar-you-zone`.
- **CTA**: `<Link href="/workspace/{slug}/items/new" aria-label="New item">` with primary styling. Sits between the two zones (borderless separator).
- **You zone**: only `UserMenu`. Sign-out, theme, and profile controls live inside the user menu (already migrated in EP-21 F-7).
- **Workspace zone**: nav items (Dashboard, Items, Inbox, Teams, Admin) + workspace name + NotificationBell. When the workspace changes, only this zone re-points; You zone is untouched.
- **No duplicated controls** — enforced by test `UserMenu appears exactly once across the sidebar`.

## F-5 — Inbox full-width

Already shipped (2026-04-18): `PageContainer` variant swapped from `narrow` to `wide` (`max-w-screen-2xl`). Mobile padding preserved. No other inbox functionality changed.

## F-7 — Work item detail redesign

### Component boundary
New component: `components/detail/item-detail-shell.tsx` (`ItemDetailShell`). It **does not** replace `WorkItemDetailLayout` at page level yet — integration is deferred. `ItemDetailShell` is tested in isolation.

### Layout
- **Desktop (≥1024px)**: left column = `ChatPanel` (fixed 40%), right column = template + top navbar + tabs panels. Chat is rendered **once** and never remounts when tabs switch.
- **Mobile (<1024px)**: "Chat" becomes the first tab in the existing tablist (single tablist, as required by `getByRole('tablist')` returning one element). Selecting Chat hides the template column; selecting any other tab hides the chat column. This avoids having two separate tablists on mobile.

### Top navbar tabs
`Template` (default), `Comments`, `Reviews`, `Timeline`, `Adjuntos`, `Spec completeness`, `Diff`, `Dependencies`, `History`.

- **Keyboard nav**: `ArrowLeft` / `ArrowRight` with wrap. `roving tabindex` — active tab is `tabIndex=0`, others `tabIndex=-1`.
- **All tabpanels** are rendered in DOM (`hidden` when inactive) so `aria-controls` resolves for every tab — needed for screen readers regardless of active state.

### Template fallback
When `workItem.type` is missing or not in `KNOWN_ITEM_TYPES`, the Template tab renders the literal string **"No template — using generic view."** above the work item description. Literal (not translated) to keep the contract explicit and match the acceptance criteria.

### Deferred (for next session)
- **Page integration**: swapping `WorkItemDetailPage` (app/workspace/[slug]/items/[id]/page.tsx) to render `ItemDetailShell` will break ~6 pre-existing test files (`detail-page.test.tsx`, `work-item-detail*.test.tsx`). That migration is its own task.
- **Sidebar auto-collapse on detail page**: tied to the page-integration step above.
- **Status strip** (lock badge, completeness pill, item type, assignee): partially wired (`LockBadge` is there but `locked=false` placeholder). Needs `useSectionLock` hook usage once page integration lands.
- **Action group** (Save / Lock / More): only `Edit` button is wired. Consolidation deferred to page integration.
- **DiffViewer**: current `DiffViewer` is a Dialog. The Diff tab renders a stub "Select a version from the History tab to compare." until we pick an inline diff component or wire the dialog via a trigger.

## Non-decisions (explicitly kept from proposal)

- i18n: no new copy is internationalized beyond existing strings. CTA text is literal "New item" by choice (F-4 proposal line).
- Mobile-first redesign: out of scope.
- Superadmin cross-workspace audit view: separate epic.
