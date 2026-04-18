# EP-17 Frontend Tasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `LockBadge`, `SeverityBadge` (for lock banners), `TypedConfirmDialog` (for force-release with reason composed in body), `HumanError` (for heartbeat failures + connection issues), semantic tokens, i18n `i18n/es/lock.ts`. Do not introduce local lock badges, raw color classes, or English strings. See `tasks/extensions.md#EP-19`.

## Progress Tracking

Update checkboxes after each step. Format: `[x] Step — note (YYYY-MM-DD)`.

---

## Group 0: Setup & Types

- [x] Create `src/types/lock.ts`: `SectionLockDTO`, `SectionLockSummary`, envelope types, `LockErrorCode` — lib/types/lock.ts (2026-04-18). NOTE: unlock-request/respond/SSE event types deferred — backend has no those endpoints yet.
- [x] Create `src/api/lock-api.ts`: typed API client for 5 actual endpoints (acquire, heartbeat, release, force-release, list) — lib/api/lock-api.ts, tested in __tests__/lib/api/lock-api.test.ts 13 tests (2026-04-18)
- [ ] Extend `WorkItemListItem` type with optional `lock: LockSummaryDTO | null` — DEFERRED: list API does not embed lock in work-item list response; needs backend change
- [ ] **RED** — Write type tests (compile-time only) — DEFERRED: no `any` already enforced by strict TS; no separate test file needed

---

## Group 1: `useSectionLock` Hook

- [x] **RED+GREEN** — Tests for `useSectionLock` — __tests__/hooks/work-item/use-section-lock.test.ts, 9 tests (2026-04-18):
  - acquires lock and sets isHolder=true
  - starts heartbeat interval after acquire
  - releases lock and sets isHolder=false
  - sets lockLost=true on heartbeat 404
  - sets lockLost=true on heartbeat 403
  - does not set lockLost on 503 (interval continues)
  - does not call DELETE if already lockLost on releaseLock
  - stops heartbeat after lockLost

- [x] Implement `hooks/work-item/use-section-lock.ts` — acquire/heartbeat/release, LOCK_HEARTBEAT_INTERVAL_MS=30000, unmount cleanup (2026-04-18)
- [x] **GREEN** — 9/9 tests pass
- [x] **REFACTOR** — No `any`, strict types, pure state/side-effects

NOTE: renamed `useWorkItemLock` → `useSectionLock` to match actual backend model (section-level, not work-item-level). 503 toast deferred — needs HumanError/toast context (EP-19 dependency).

---

## Group 2: `LockBadge` Component

- [x] **RED+GREEN** — Basic tests in __tests__/components/domain/misc-badges.test.tsx (renders locked/unlocked, shows lockedBy) — 3 tests pass (pre-existing, 2026-04-18)
- [x] Implement `components/domain/lock-badge.tsx` — simple pill badge with Lock icon, lockedBy text, role="img" (pre-existing, 2026-04-18)
- [ ] Full spec badge (initials, tooltip, 48dp touch target, mobile tap → onRequestUnlock) — DEFERRED: requires unlock-request flow which needs backend unlock-request endpoints

---

## Group 3: `LockBanner` Component

- [x] **RED+GREEN** — 7 tests in `__tests__/components/locks/lock-banner.test.tsx` — all pass (2026-04-18)
- [x] Implement `components/locks/lock-banner.tsx` — inline banner with holder name, relative time, optional unlock-request button, `role="status"` (2026-04-18)
- [x] **GREEN** — 7/7 tests pass (2026-04-18)

---

## Group 4: `useRelativeTime` Hook (shared utility)

- [x] **RED+GREEN** — Tests in __tests__/components/domain/relative-time.test.tsx (renders time element, datetime attr, has text) — 3 tests pass (pre-existing, 2026-04-18)
- [x] Implement `hooks/use-relative-time.ts` + `components/domain/relative-time.tsx` — updates at 1Hz, respects prefers-reduced-motion, Spanish locale (pre-existing, 2026-04-18)

---

## Group 5: `UnlockRequestDialog` Component

- [x] **RED+GREEN** — 10 tests in `__tests__/components/locks/unlock-request-dialog.test.tsx` — all pass (2026-04-18)
- [x] Implement `components/locks/unlock-request-dialog.tsx`
  - Props: `sectionId: string`, `holderDisplayName: string`, `isOpen: boolean`, `onClose: () => void`
  - Reason `<textarea>`: required, max 500 chars enforced, character counter
  - Submit disabled when reason empty or submitting
  - On success: close + toast with holder name
  - On `409`: inline alert error
  - On `429`: inline alert error with retry-after minutes
  - `role="dialog"` via Dialog component, Escape closes
- [x] **GREEN** — 10/10 tests pass (2026-04-18)
- [x] Extended `lib/types/lock.ts` with `UnlockRequestDTO`, `UnlockRequestEnvelope`, `RespondToRequestBody` (2026-04-18)
- [x] Extended `lib/api/lock-api.ts` with `requestSectionUnlock`, `respondToUnlockRequest` (2026-04-18)

---

## Group 6: `HolderResponsePanel` Component

- [x] **RED+GREEN** — 9 tests in `__tests__/components/locks/holder-response-panel.test.tsx` — all pass (2026-04-18)
- [x] Implement `components/locks/holder-response-panel.tsx`
  - Props: `sectionId: string`, `request: UnlockRequestDTO`, `requesterDisplayName: string`, `onRespond: (decision: 'release' | 'ignore') => void`
  - Countdown from `request.expires_at` via `setInterval` at 1s, formatted as mm:ss
  - Release button (destructive): calls `respondToUnlockRequest` with `action=accept`, triggers `onRespond('release')`
  - Ignore button (outline): calls `respondToUnlockRequest` with `action=decline`, triggers `onRespond('ignore')`
  - NOT dismissible: no Escape handler, no click-outside
  - `role="alertdialog"`, `aria-modal="false"` — inline panel
- [x] **GREEN** — 9/9 tests pass (2026-04-18)
- Note: `test_panel_injected_on_unlock_requested_sse_event` — SSE wiring belongs in Group 8 (detail page integration); panel itself is standalone and tested

---

## Group 7: `ForceReleaseDialog` Component (Admin)

- [x] **RED+GREEN** — 9 tests in `__tests__/components/locks/force-release-dialog.test.tsx` — all pass (2026-04-18)
- [x] Implement `components/locks/force-release-dialog.tsx`
  - Props: `sectionId: string`, `lock: SectionLockDTO`, `holderDisplayName: string`, `currentUser: AuthUser`, `isOpen: boolean`, `onClose: () => void`
  - Gate: `currentUser.is_superadmin` (capabilities.force_unlock pending RBAC — EP-10 TODO)
  - Lock summary with holder name + RelativeTime for acquired_at and expires_at
  - Reason textarea: min 10 chars, max 1000 chars
  - Confirmation checkbox with holder name substituted
  - Submit disabled until reason valid AND checkbox checked
  - On success: close + toast "Bloqueo liberado correctamente."
  - On 503: inline alert error
- [x] **GREEN** — 9/9 tests pass (2026-04-18)
- Note: BE force-release endpoint does not yet accept reason param (TODO in lock_controller.py). Reason is validated UI-side only until BE adds it.

---

## Group 8: Lock Integration in Detail Page Edit Flow (DEFERRED — specification tab has read-only lock indicator; full acquire-on-edit-click needs useSectionLock wired to SectionEditor, scoped to ~2h work)

- [ ] **RED** — Write integration tests for `WorkItemDetailPage` edit flow:
  - `test_clicking_edit_acquires_lock`
  - `test_edit_mode_shows_editing_indicator_with_countdown`
  - `test_edit_mode_starts_heartbeat`
  - `test_cancel_releases_lock`
  - `test_save_releases_lock_on_success`
  - `test_navigation_away_releases_lock`
  - `test_lock_banner_shown_when_item_already_locked_on_mount`
  - `test_lock_banner_appears_on_lock_acquired_sse_event`
  - `test_lock_banner_disappears_on_lock_released_sse_event`
  - `test_holder_response_panel_shown_on_unlock_requested_sse_event`
  - `test_force_release_dialog_shown_for_admin`

- [ ] Integrate `useWorkItemLock` into `WorkItemDetailPage`:
  - "Edit" button → `acquireLock()`, on success → enter edit mode
  - On `409 LOCK_HELD`: do NOT enter edit mode, show `LockBanner`
  - On `409 LOCK_HELD_BY_SELF`: show confirmation prompt
  - In edit mode header: "Editing… · Lock expires in {countdown}"
  - Cancel button: `releaseLock()` → exit edit mode
  - Save success: `releaseLock()` after successful save
  - `useEffect` with `router.events.on('routeChangeStart')`: release lock before navigation
  - Subscribe to SSE `sse:work_item:{id}` for lock events
  - On `lock_acquired`: show `LockBanner`, disable edit
  - On `lock_released`: hide `LockBanner`, enable edit
  - On `unlock_requested` (only if `isHolder`): show `HolderResponsePanel`
  - On `lock_force_released` (only if `isHolder`): trigger lock-loss recovery UX
  - Show `ForceReleaseDialog` trigger for users with `force_unlock` capability

- [ ] **GREEN** — All integration tests pass

---

## Group 9: Lock Badges in List View (DEFERRED — list API does not embed lock field; backend change required)

- [ ] **RED** — Write tests for list row rendering:
  - `test_lock_badge_rendered_when_lock_field_is_non_null`
  - `test_no_badge_when_lock_is_null`
  - `test_badge_updates_when_sse_event_received_for_item_in_view`

- [ ] Add `LockBadge` to `WorkItemListRow` component
  - Read `lock` field from list API response (embedded, no extra request)
  - On `LockBadge` click (mobile): open `UnlockRequestDialog`
  - List view SSE update: update lock state on `lock_acquired`/`lock_released` events — either via workspace-level SSE channel or on-focus re-fetch

- [ ] **GREEN** — List badge tests pass

---

## Group 10: Lock-Loss Recovery UX (DEFERRED — depends on Group 8 integration and react-hook-form draft capture)

- [ ] **RED** — Write tests:
  - `test_lock_lost_banner_shown_on_heartbeat_404`
  - `test_lock_lost_banner_shown_on_lock_force_released_sse`
  - `test_unsaved_draft_serialized_in_readonly_textarea`
  - `test_copy_to_clipboard_copies_draft`
  - `test_draft_not_auto_discarded`
  - `test_lock_lost_banner_persistent_does_not_auto_dismiss`
  - `test_correct_reason_shown_for_force_release_vs_expiry`

- [ ] Implement lock-loss recovery banner (inline in `WorkItemDetailPage` or as `LockLostRecoveryBanner` component)
  - Persistent (no auto-dismiss)
  - Content: "Your editing session ended. {reason}. Your unsaved changes are below — copy them before refreshing."
  - Read-only `<textarea>` with serialized draft content
  - "Copy to clipboard" button → `navigator.clipboard.writeText(draft)`
  - Draft source: last known form state from `react-hook-form` or equivalent
  - Reason varies: "due to inactivity" (TTL expiry), "An admin released your lock. Reason: {reason}" (force), "The lock was released by another session" (heartbeat failure)

- [ ] **GREEN** — Recovery UX tests pass

---

## Group 11: Accessibility Audit

- [x] `SectionEditor` lock indicator uses `role="status"` and `aria-label="Bloqueado por {name}"` (pre-existing, 2026-04-18)
- [x] `LockBadge` uses `role="img"` with `aria-label` (pre-existing, 2026-04-18)
- [ ] 48dp touch targets, keyboard nav, HolderResponsePanel a11y — DEFERRED pending Groups 5-8

---

**Status: PARTIAL** (2026-04-18) — Foundation + G3/G5/G6/G7 shipped. Types extended, API client extended (unlock-request/respond), LockBanner, UnlockRequestDialog, HolderResponsePanel, ForceReleaseDialog — 35 new tests, all GREEN. Remaining: Groups 8 (detail page integration), 9 (list badge), 10 (lock-loss recovery), 11 (a11y audit).

## Acceptance Criteria Checklist

- [ ] "Edit" button click acquires lock and starts heartbeat within 1 interaction
- [ ] Heartbeat fires every 30s and extends TTL
- [ ] Lock released on any exit from edit mode (cancel, save, navigation, tab close)
- [ ] `LockBanner` appears within 1 second of SSE `lock_acquired` event (no reload)
- [ ] `LockBadge` in list view populated from initial fetch (no N+1 per row)
- [ ] Lock-loss recovery banner preserves unsaved draft
- [ ] `ForceReleaseDialog` requires reason (min 10 chars) AND confirmation checkbox
- [ ] Admin force-release dialog hidden for non-admin users
- [ ] `HolderResponsePanel` not dismissible by Escape or click-outside
- [ ] All components render without horizontal scroll at 375px
- [ ] All interactive elements meet 48dp touch target
- [ ] RED phase committed before each implementation step
