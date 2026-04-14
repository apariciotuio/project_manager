# Frontend Review

**Date**: 2026-04-13
**Scope**: EP-00 through EP-12, all tasks-frontend.md files + responsive spec
**Reviewer**: frontend-developer agent

---

## UX Critical (users will get stuck or confused)

### UC-1. No global navigation architecture defined until EP-12 — but EP-01 through EP-11 reference routes

EP-12 Group 1 defines `AppShell` with bottom nav (mobile) and sidebar (desktop). Every prior epic references routes like `/workspace/{slug}/work-items/{id}`, `/workspace/{slug}/teams`, `/workspace/{slug}/inbox`. But the nav items themselves (what's in the bottom bar, what's in the sidebar) are only named in the responsive spec as "Inbox, Search, Notifications, Profile" — no mention of Dashboard, Admin, Work Items list as primary nav anchors.

**Fix**: EP-12 `AppShell` must define the full nav item set with capability guards (Admin nav items hidden if no admin capabilities). Document this in EP-12 tasks-frontend.md Group 1.

### UC-2. EP-03 suggestion polling is 2s fixed interval — user has no feedback on wait time

EP-03 Phase 8: "poll `getSuggestionSet(set_id)` every 2s while status is `pending`". There's no maximum wait time, no "this may take a while" message, and no timeout fallback. LLM generation can take up to 15s (per tech_info.md). The user is staring at a loading skeleton for up to 7-8 poll cycles with no indication of progress.

**Fix**: EP-03 tasks-frontend.md Phase 8: use `useJobProgress` (EP-12 Group 9, which provides SSE-based progress) instead of polling. If polling is kept, add a timeout after 30s: replace skeleton with "Taking longer than expected — you'll be notified when ready" and stop polling.

### UC-3. EP-06 Group 4: SubmitReviewPanel returns null for non-reviewers — reviewer is determined solely on `reviewer_id` but team reviews use `team_id`

EP-06 Group 4 acceptance criteria: "WHEN `currentUserId` is not the `reviewer_id`... THEN component renders nothing." But `ReviewRequest.reviewer_type` can be `team`, in which case `reviewer_id` is null and `team_id` is set. The check `currentUserId !== reviewer_id` will always be true for team reviews, hiding the panel from every team member.

**Fix**: EP-06 tasks-frontend.md Group 4: `SubmitReviewPanel` must check both: `reviewer_type === 'user' && currentUserId === reviewer_id` OR `reviewer_type === 'team' && currentUserTeamIds.includes(team_id)`. The hook or parent must pass `currentUserTeamIds` as a prop.

### UC-4. EP-02 auto-save has no visible "saving" / "saved" indicator in the committed-item edit flow

EP-02 defines `useAutoSave` with `isSaving` and `lastSavedAt`, and the hook returns them — but the `WorkItemHeader` and `SectionEditor` (EP-04) never reference them. Users editing a committed work item have no way to know if their changes were persisted before navigating away.

**Fix**: EP-04 tasks-frontend.md `SectionEditor`: add "Saving..." / "Saved at HH:MM" status text below the save button, driven by `isSaving` and `lastSavedAt` from `useAutoSave`.

### UC-5. EP-01 CreateWorkItemPage Cancel has no guard when form has content

EP-01 Phase 8: "WHEN Cancel is clicked THEN `router.back()` is called AND if the form has content, no confirmation is required (EP-02 adds this)." EP-02 does not add this. The EP-02 definition of done has no item for "confirm unsaved changes on cancel". Users can lose typed content with a single click.

**Fix**: EP-02 tasks-frontend.md Phase 6: add acceptance criteria — "WHEN Cancel is clicked AND the form has unsaved content (title non-empty OR description non-empty) THEN a confirmation dialog shows before discarding."

### UC-6. EP-08 quick action `endpoint`/`method` fields are in the `QuickAction` interface but security review (HIGH-6) flags this as an SSRF vector

EP-08 `QuickAction` interface in tasks-frontend.md includes `endpoint: string` and `method: string`. The security review requires these become an enum of known actions. But the frontend `NotificationItem` and `InboxTierSection` reference `quick_action.action` for button labels — if the action type becomes an enum, the button label logic changes.

**Fix**: EP-08 tasks-frontend.md Group 1: update `QuickAction` interface — remove `endpoint` and `method`, replace with `action_type: 'APPROVE_REVIEW' | 'MARK_READ' | 'ASSIGN_TO_ME'`. Update `executeAction` to send `{ action_type }` not arbitrary endpoint/method. Update Group 5 and Group 6 label rendering.

### UC-7. EP-05 dependency picker in `DependenciesPanel` asks user to enter a "task ID" — this is terrible UX

EP-05 Group 5 acceptance criteria: "add dependency input with task ID selector." Task IDs are UUIDs. No user knows task UUIDs. The test at 5.3 says "task ID selector" which implies a search/autocomplete, but the component spec doesn't define what the input looks like.

**Fix**: EP-05 tasks-frontend.md Group 5, item 5.3: `DependenciesPanel` dependency input must be a **typeahead search** over `GET /api/v1/work-items/:id/task-tree` results, searching by task title. Clarify this explicitly — "task title search, not raw ID entry."

### UC-8. EP-09 QuickViewPanel on mobile renders as BottomSheet but EP-09 detail page also navigates to full detail — two flows for the same action

EP-09 Group 1: "On mobile: render as `BottomSheet`." But EP-12 responsive spec Scenario 1: "WHEN the user taps a card THEN full-screen navigation to element detail occurs (no side panel)." These contradict each other. On mobile, does a card tap open a BottomSheet or navigate?

**Fix**: EP-09 tasks-frontend.md Group 1 QuickViewPanel: mobile should navigate directly to `/work-items/{id}` (full detail), not open a BottomSheet. BottomSheet is for the desktop quick-view side panel experience. Document this explicitly.

---

## Component Architecture Issues

### CA-1. Duplicate `useWorkItems` / `useWorkItem` hooks defined in EP-01 and again in EP-09

EP-01 Phase 3 defines `useWorkItem(id)` and `useWorkItems()` at `src/hooks/use-work-item.ts`. EP-09 Group 6 defines `useWorkItemDetail(id)` and `useWorkItems(filters)` again. These will have different cache keys, different return shapes, and will cause stale data issues — editing from EP-01 won't invalidate the EP-09 list.

**Fix**: EP-09 tasks-frontend.md Group 6: delete the `useWorkItemDetail` and `useWorkItems` hook definitions. Use the hooks from EP-01. If EP-09 needs different filter shapes or additional fields from the summary endpoint, extend EP-01's hooks with optional params, not new hooks.

### CA-2. `AssignOwnerButton` in EP-08 Group 7 duplicates `ReassignOwnerModal` from EP-01 Phase 6

Both components do the same thing: pick a workspace member and assign them as owner of a work item. Two separate implementations means two separate user search inputs, two inconsistent UXes for the same action.

**Fix**: EP-01 `ReassignOwnerModal` should be the canonical owner-picker. EP-08's `AssignOwnerButton` should reuse it (or a shared `UserPicker` component), not reimplement member search. EP-08 tasks-frontend.md Group 7, item 7.2: replace custom implementation with shared `UserPicker` from EP-01.

### CA-3. `StateChip` / `TypeBadge` / `CompletenessBar` defined in EP-01 WorkItemCard AND redefined in EP-02 WorkItemHeader

EP-01 Phase 4 `WorkItemCard` includes `TypeBadge`, `StateChip`, `CompletenessBar`. EP-02 Phase 5 `WorkItemHeader` re-implements all three as sub-components. These should be in a shared component file (`src/components/work-items/shared/`), not duplicated.

**Fix**: EP-01 tasks-frontend.md Phase 4: extract `TypeBadge`, `StateChip`, `CompletenessBar` to `src/components/work-items/badges.tsx`. EP-02 `WorkItemHeader` imports them. EP-09 `WorkItemCard` imports them. One source of truth.

### CA-4. EP-03 `streamThread` SSE client and EP-08 `useSSENotifications` both implement `EventSource` with exponential backoff reconnect independently

Two separate SSE client implementations. EP-12 defines `useJobProgress` as a third. The reconnect logic (backoff intervals, cleanup) should be a shared primitive.

**Fix**: EP-12 tasks-frontend.md Group 9: extract `createSSEClient(url, handlers, reconnectOptions)` as a reusable utility in `src/lib/sse-client.ts`. EP-03's `streamThread`, EP-08's `useSSENotifications`, and EP-12's `useJobProgress` all use it. This is the single place backoff logic lives.

### CA-5. Form validation pattern is inconsistent across epics

EP-05 Group 4 uses `react-hook-form + zod`. EP-01 Phase 8, EP-02 Phase 4, EP-06 Group 3 use unspecified custom validation. EP-04's section editor uses manual `length` checks. Pick one and mandate it.

**Fix**: Standardize on `react-hook-form + zod` across all form components. Define this in EP-12 tasks-frontend.md as a project standard. All form components (ForceReadyModal, CaptureForm, RequestReviewDialog, etc.) should use `zodResolver`.

---

## Missing UI Patterns

### MU-1. No toast/notification system defined

Multiple epics reference "toast" notifications: EP-06 "Item is now Ready toast", EP-11 "Export queued" toast, EP-08 "STALE_ACTION toast error". No epic defines the toast component or how toasts stack, dismiss, or relate to SSE notifications. This will be reinvented per-epic.

**Fix**: EP-12 tasks-frontend.md Group 1: add `ToastProvider` and `useToast()` hook as a layout primitive. Define variants: success, error, warning, info. Max 3 visible at once. Auto-dismiss after 5s. All epics call `useToast().show()` — no custom toast implementations.

### MU-2. EP-07 anchored comment selection mechanism is completely unspecified

EP-07 Group 4 item 4.7: "section editor renders comment count badge on selected text ranges." There is zero specification of how the user selects text in a section to create an anchor. What triggers the anchor creation UI? A popover on mouse-up? A toolbar? On mobile, text selection is notoriously inconsistent.

**Fix**: EP-07 tasks-frontend.md Group 4 item 4.8: add acceptance criteria — "WHEN a user selects text in a `SectionEditor` and releases the mouse THEN a 'Comment' button appears in a floating popover above the selection AND clicking it opens `AnchoredCommentPopover` pre-filled with the selection data." Specify that on mobile this is disabled (too unreliable) and users can only post general comments.

### MU-3. EP-05 drag-to-reorder uses "native drag events" — this will break on touch devices

EP-05 Group 3 item 3.6: "drag-to-reorder using native drag events (no heavy DnD library at MVP)." Native HTML5 drag events do not fire on touch/mobile. The spec at Group 7 item 7.1 says "drag-to-reorder disabled on touch" but that means mobile users cannot reorder tasks at all.

This is acceptable for MVP but needs a mobile alternative — at minimum, up/down arrow buttons on each task node.

**Fix**: EP-05 tasks-frontend.md Group 3: add item — "On touch devices (mobile breakpoint): render up/down reorder buttons on each `TaskTreeNode` in place of drag handle. Buttons call `reorderTasks` with adjacent swap."

### MU-4. No "loading more" / infinite scroll pattern standardized — each epic implements differently

EP-07 `CommentFeed` has "Load more" button. EP-09 list has "Load more" button. EP-12 inbox has "Load more or infinite scroll." Different epics will implement this differently.

**Fix**: EP-12 tasks-frontend.md Group 1: add `LoadMoreButton` as a layout primitive with consistent props: `isLoading`, `hasMore`, `onLoadMore`. Wire cursor pagination uniformly.

### MU-5. EP-10 `MemberCapabilityEditor` has 10 checkboxes but no capability descriptions

Users won't know what `CONFIGURE_INTEGRATION` or `VIEW_AUDIT_LOG` means from the name alone. No tooltip or description is specified.

**Fix**: EP-10 tasks-frontend.md Group 2: add acceptance criteria — "WHEN a capability checkbox renders THEN a `?` icon with a tooltip describes what the capability allows (e.g., 'Configure Jira integrations and manage project mappings')." Define the description strings in a constant.

### MU-6. EP-09 pipeline view has no item cap UI feedback

EP-09 Group 4 tests "items capped at 20" but there's no specified UI for "and 15 more not shown." User can't tell the pipeline is truncated.

**Fix**: EP-09 tasks-frontend.md Group 4: add acceptance criteria — "WHEN a pipeline column has more than 20 items THEN a '+ N more' link renders at the bottom of the column that navigates to the filtered list view."

---

## State Management Gaps

### SM-1. Cache invalidation between EP-01 state transitions and EP-09 list view is unspecified

When `transitionState()` succeeds in EP-01 `useTransitionState`, it invalidates `['work-item', id]`. But EP-09's `useWorkItems` has cache key `['work-items', filters]`. EP-01's mutation does not invalidate the list. The list will show stale state until the 60s refetch.

**Fix**: EP-01 tasks-frontend.md Phase 3 `useTransitionState`: on success, also invalidate `['work-items']` (all list queries). The work item's state changed — the list reflects wrong state otherwise.

### SM-2. EP-04 completeness cache invalidation is incomplete — EP-03 suggestion apply also changes sections

EP-04 `useUpdateSection` mutation invalidates completeness. But EP-03 `applySuggestions` also writes sections (triggers `suggestion.applied` → `section_updated`). EP-03 has no invalidation of completeness or specification caches.

**Fix**: EP-03 tasks-frontend.md Phase 6 `SuggestionPreviewPanel`: on `applySuggestions()` success, invalidate `['specification', workItemId]` and `['completeness', workItemId]` caches.

### SM-3. EP-08 SSE `notification_created` updates the notification list cache but not inbox cache — inbox shows stale data

EP-08 Group 3: SSE `notification_created` prepends to `useNotifications` cache and increments unread count. But `useInbox` is a separate query. A new review notification won't appear in the inbox tier until `useInbox.refresh()` is explicitly called.

The `inbox_count_updated` SSE event triggers a lazy cache invalidation for the inbox, but this only fires as a separate event — if the backend only sends `notification_created`, the inbox is never refreshed.

**Fix**: EP-08 tasks-frontend.md Group 3: on `notification_created` SSE event, also invalidate `useInbox` cache if `notification.subject_type` is `review` or `block` (inbox-relevant types).

### SM-4. EP-06 review submission invalidates `work_item` state cache but EP-09 detail page has its own `useWorkItemDetail` cache key

As called out in CA-1, EP-09 defines its own hooks. If EP-06's `useSubmitReview` invalidates `['work-item', id]` (EP-01 key) but EP-09 detail page uses `['work-item-detail', id]`, the detail page won't update after a review is submitted.

**Fix**: Resolved by CA-1 fix (unify hooks). If hooks remain separate, EP-06 tasks-frontend.md Group 2: `useSubmitReview` must invalidate both cache keys.

### SM-5. EP-03 polling for suggestion set uses 2s fixed interval with no cleanup on navigation

EP-03 Phase 8: "poll `getSuggestionSet(set_id)` every 2s while status is pending." This polling is set up in the page component but there's no specification of what happens when the user navigates away mid-poll. React Query will continue polling until unmount, but if the component is inside a tab layout (which it is in EP-04 Phase 8), tab switches don't unmount components by default in Next.js App Router.

**Fix**: EP-03 tasks-frontend.md Phase 8: use React Query `refetchInterval` with `refetchIntervalInBackground: false` so polling pauses when tab is not focused. Cap polling at 60s max then switch to "notify via SSE" approach.

---

## Mobile/Responsive Gaps

### MR-1. EP-07 version diff viewer on mobile is "version list collapses to dropdown; diff viewer scrollable" — no test specified

EP-07 Group 7 item 7.5 specifies mobile behavior in prose but has no RED test item. It won't be verified.

**Fix**: EP-07 tasks-frontend.md Group 7: add `[RED]` tests: "version list renders as `<select>` dropdown on viewport <640px; diff viewer is vertically scrollable on mobile with no horizontal overflow."

### MR-2. EP-05 task tree on mobile collapses to flat list — but flat list of 50+ tasks is unusable without hierarchy

EP-05 Group 7 item 7.1: "tree collapses to flat list sorted by `display_order`." If a work item has 40 tasks with 3 levels of nesting, a flat list of 40 items sorted by display_order gives no parent context. The `breadcrumb` field exists but isn't mentioned in the mobile view.

**Fix**: EP-05 tasks-frontend.md Group 7 item 7.1: flat list items on mobile must show the `breadcrumb` path (e.g., "Backend > Auth > Login") as a secondary line. Add test: "mobile task list item renders breadcrumb trail as subtitle text."

### MR-3. EP-04 `CompletenessPanel` dimension rows "collapse to icon-only on mobile" — icon-only state has no specification

EP-04 Phase 9: "dimension rows collapse to icon-only on mobile (< 768px) with tooltip on hover/tap." Icons for what? Filled/unfilled? There's no icon set defined. Tooltip on tap is unreliable UX on touch (requires two taps: one to show tooltip, one to dismiss).

**Fix**: EP-04 tasks-frontend.md Phase 9: instead of icon-only, collapse to a compact one-line format showing dimension name truncated + a filled/unfilled dot. Replace tooltip with a tap-to-expand that shows the full dimension detail inline.

### MR-4. EP-10 admin section has no mobile strategy beyond "hamburger drawer"

EP-10 Group 1: "admin side navigation collapses to hamburger/drawer." The admin section has 8 subsections (Members, Rules, Projects, Integrations, Audit Log, Dashboard, Support, Health). All of them use `DataTable` which EP-12 specifies scrolls horizontally. The audit log diff expansion, capability editor checkbox grid, and sync log table are all complex desktop-first UIs with no mobile equivalents specified.

Admin being desktop-only is acceptable for MVP, but this needs to be explicit.

**Fix**: EP-10 tasks-frontend.md Group 1: add explicit statement — "Admin section targets desktop (md+) as the primary viewport. Mobile access is supported (no horizontal overflow at page level) but admin flows are not optimized for mobile in MVP."

### MR-5. EP-12 responsive spec Scenario 5 mentions long-press context menus — no epic implements this

EP-12 spec Scenario 5: "WHEN a user long-presses a table row or card on mobile THEN a context menu appears." No epic's tasks-frontend.md implements long-press behavior anywhere. This is either out of scope or needs adding to EP-09 WorkItemCard and EP-08 InboxTierSection.

**Fix**: Either remove this from EP-12 spec Scenario 5 (mark as post-MVP) or add a single implementation note in EP-09 WorkItemCard and EP-08 InboxTierSection: "long-press triggers context menu with primary actions."

---

## Strengths (well-designed patterns to preserve)

1. **EP-00 auth flow** — HTTP-only cookies, presence-only cookie check in middleware, hard navigation for OAuth. Clean and correct.
2. **EP-02 `useAutoSave`** — debounce via `useRef` + `setTimeout` (no lodash), conflict resolution with explicit `onConflict` callback, cleanup on unmount. Solid hook design.
3. **EP-03 SSE stream cleanup** — explicit `EventSource.close()` on unmount specified in tests and acceptance criteria. Will prevent memory leaks.
4. **EP-08 SSE exponential backoff** — 1s, 2s, 4s, max 30s, new token fetch before reconnect. Correct and complete.
5. **EP-08 Group 3** — single global `EventSource` per session mounted in root `NotificationProvider`. Correct singleton pattern.
6. **EP-06 `useTransitionToReady`** — surfaces `blockingRules` as a dedicated field, plus `triggerOverride(justification)` function. Clean hook API that makes the UI straightforward to implement.
7. **EP-12 Group 1 layout primitives** — `AppShell`, `BottomSheet`, `SkeletonLoader`, `EmptyState`, `ErrorBoundary` as shared primitives with the explicit dependency note. Correct architecture.
8. **EP-09 search** — 300ms debounce, 2-char minimum, URL param sync, scroll position preservation. All four done correctly.
9. **EP-07 `VersionCompareSelector`** — prevents `from > to` at the component level (swap or disable). Correct defensive UI.
10. **EP-03 `SuggestionPreviewPanel`** — per-item accept/reject in local state, single API call on "Apply Selected." Avoids N+1 API calls per toggle.

---

## Recommendations by Epic

### EP-01 tasks-frontend.md
- Phase 3 `useTransitionState`: also invalidate `['work-items']` list cache on success. (SM-1)
- Phase 4 `WorkItemCard`: extract `TypeBadge`, `StateChip`, `CompletenessBar` to shared file. (CA-3)
- Phase 6 `ReassignOwnerModal`: make this the shared owner-picker used by EP-08 as well. (CA-2)

### EP-02 tasks-frontend.md
- Phase 6: add acceptance criteria for cancel confirmation when form has content. (UC-5)

### EP-03 tasks-frontend.md
- Phase 6 `SuggestionPreviewPanel`: on `applySuggestions()` success, invalidate `['specification', workItemId]` and `['completeness', workItemId]`. (SM-2)
- Phase 8: replace 2s polling with `useJobProgress` SSE hook or add 30s timeout + fallback message. (UC-2, SM-5)
- `src/lib/api/sse-client.ts`: this is the canonical SSE utility — EP-08 and EP-12 should reuse it, not reimplement. (CA-4)

### EP-04 tasks-frontend.md
- `SectionEditor`: add "Saving..." / "Saved at HH:MM" status indicator driven by `useAutoSave`. (UC-4)
- Phase 9: replace "icon-only on mobile" with compact one-line format for dimension rows. (MR-3)

### EP-05 tasks-frontend.md
- Group 5 `DependenciesPanel` item 5.3: dependency input is a **title-based typeahead search**, not a raw ID field. (UC-7)
- Group 3 item 3.6: add up/down reorder buttons for touch devices. (MU-3)
- Group 7 item 7.1: flat mobile list items must show `breadcrumb` as subtitle. (MR-2)

### EP-06 tasks-frontend.md
- Group 4 `SubmitReviewPanel`: fix team review visibility — check `team_id` + `currentUserTeamIds`, not just `reviewer_id`. (UC-3)
- Group 2: if EP-09 hooks remain separate, invalidate both cache key variants after review submission. (SM-4)

### EP-07 tasks-frontend.md
- Group 4 item 4.8: add acceptance criteria for text selection → anchor creation flow. Explicitly disable on mobile. (MU-2)
- Group 7: add `[RED]` tests for mobile version diff behavior. (MR-1)

### EP-08 tasks-frontend.md
- Group 1: update `QuickAction` interface — replace `endpoint`/`method` with `action_type` enum per security review HIGH-6. (UC-6)
- Group 3: on `notification_created` SSE event, also invalidate `useInbox` cache for review/block notification types. (SM-3)
- Group 7: consolidate `AssignOwnerButton` to reuse `UserPicker` from EP-01 `ReassignOwnerModal`. (CA-2)

### EP-09 tasks-frontend.md
- Group 1 QuickViewPanel: mobile = full navigation, not BottomSheet. (UC-8)
- Group 6: delete `useWorkItemDetail` and `useWorkItems` — use EP-01 hooks. (CA-1)
- Group 4: add "N more items" link to pipeline columns capped at 20. (MU-6)

### EP-10 tasks-frontend.md
- Group 1: add explicit "admin section is desktop-primary in MVP" statement. (MR-4)
- Group 2 `MemberCapabilityEditor`: add capability description tooltips. (MU-5)

### EP-11 tasks-frontend.md
- No structural issues. Export status polling is correctly deferred (accordion lazy load). Capability guard on retry button is correctly specified.

### EP-12 tasks-frontend.md
- Group 1: add `ToastProvider` + `useToast()` as a layout primitive. (MU-1)
- Group 1: add `LoadMoreButton` as a layout primitive for cursor pagination. (MU-4)
- Group 9: extract `createSSEClient` utility that EP-03 and EP-08 share. (CA-4)
- Spec Scenario 5 (long-press): explicitly mark as post-MVP or add to EP-09/EP-08. (MR-5)
- All epics: mandate `react-hook-form + zod` as the form validation standard. (CA-5)

---

## Summary Table

| Category | Count | Priority |
|----------|-------|----------|
| UX Critical (users stuck/confused) | 8 | Must fix |
| Component Architecture | 5 | Must fix |
| Missing UI Patterns | 6 | Should fix |
| State Management Gaps | 5 | Must fix |
| Mobile/Responsive Gaps | 5 | Should fix |
| Strengths | 10 | Preserve |

**Top priority fixes before implementation starts**:
1. UC-3 (team review visibility — users can't submit reviews for team-assigned items)
2. CA-1 (duplicate hooks — will cause stale data bugs)
3. SM-1 (transition invalidation — list shows wrong state)
4. UC-6 (QuickAction interface — must align with security review)
5. MU-1 (toast system — reinvented across 6 epics without this)
