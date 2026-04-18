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

- [ ] LockBanner — DEFERRED: requires unlock-request backend endpoints and SSE lock_acquired/released events. Specification tab already shows lock indicator inline on SectionEditor. Full banner is a future increment.

---

## Group 4: `useRelativeTime` Hook (shared utility)

- [x] **RED+GREEN** — Tests in __tests__/components/domain/relative-time.test.tsx (renders time element, datetime attr, has text) — 3 tests pass (pre-existing, 2026-04-18)
- [x] Implement `hooks/use-relative-time.ts` + `components/domain/relative-time.tsx` — updates at 1Hz, respects prefers-reduced-motion, Spanish locale (pre-existing, 2026-04-18)

---

## Group 5: `UnlockRequestDialog` Component (DEFERRED — backend gap)

- [ ] **RED** — Write component tests:
  - `test_renders_reason_field_required`
  - `test_submit_disabled_when_reason_empty`
  - `test_submit_enabled_when_reason_has_content`
  - `test_submit_calls_request_unlock_api`
  - `test_closes_and_shows_toast_on_success`
  - `test_shows_error_on_409_request_pending`
  - `test_shows_error_on_429_rate_limited_with_retry_after`
  - `test_reason_max_500_chars_enforced`
  - `test_dialog_accessible_focus_trap`

- [ ] Implement `src/components/locks/UnlockRequestDialog.tsx`
  - Props: `workItemId: UUID`, `holderDisplayName: string`, `isOpen: boolean`, `onClose: () => void`
  - Reason `<textarea>`: required, Zod min(1) max(500), character counter
  - Submit button: disabled when reason empty or submitting
  - Loading state during API call
  - On success: close + toast "Unlock request sent to {holder}. You'll be notified when they respond."
  - On `409`: inline error with existing request info
  - On `429`: inline error with "Try again in X minutes"
  - Focus trap within dialog, Escape closes

- [ ] **GREEN** — All dialog tests pass

---

## Group 6: `HolderResponsePanel` Component (DEFERRED — backend gap)

- [ ] **RED** — Write component tests:
  - `test_renders_requester_info_and_reason`
  - `test_shows_countdown_from_120_seconds`
  - `test_countdown_ticks_down_every_second`
  - `test_release_button_calls_respond_api_with_release`
  - `test_ignore_button_calls_respond_api_with_ignore`
  - `test_panel_not_dismissible_by_click_outside`
  - `test_panel_not_dismissible_by_escape`
  - `test_panel_injected_on_unlock_requested_sse_event`
  - `test_panel_removed_after_respond`

- [ ] Implement `src/components/locks/HolderResponsePanel.tsx`
  - Props: `request: UnlockRequestDTO`, `workItemId: UUID`, `onRespond: (decision: 'release' | 'ignore') => void`
  - Countdown derived from `request.expires_at` using `setInterval` at 1s
  - "[Avatar] {requester_display_name} is asking to edit · Reason: {reason} · Auto-releases in {mm:ss}"
  - "Release lock" button: primary, red variant — calls `respond-to-request { decision: 'release' }`
  - "Ignore" button: secondary — calls `respond-to-request { decision: 'ignore' }`
  - NOT dismissible: no click-outside handler, Escape key does nothing
  - Accessible: `role="alertdialog"`, `aria-modal="false"` (it's inline, not a modal)

- [ ] **GREEN** — All panel tests pass

---

## Group 7: `ForceReleaseDialog` Component (Admin) (DEFERRED — backend gap: no reason param, no RBAC)

- [ ] **RED** — Write component tests:
  - `test_not_rendered_for_user_without_force_unlock_capability`
  - `test_rendered_for_user_with_force_unlock_capability`
  - `test_shows_current_lock_summary`
  - `test_submit_disabled_until_reason_and_checkbox_filled`
  - `test_submit_disabled_when_reason_less_than_10_chars`
  - `test_submit_calls_force_release_api`
  - `test_success_closes_dialog_and_shows_toast`
  - `test_503_shows_error_banner`

- [ ] Implement `src/components/locks/ForceReleaseDialog.tsx`
  - Props: `workItemId: UUID`, `lock: LockDTO`, `isOpen: boolean`, `onClose: () => void`
  - Gate render on `user.capabilities.includes('force_unlock')` (from auth context)
  - Lock summary: "Currently editing: {holder_name} · Since {relativeTime(acquired_at)} · Expires {relativeTime(expires_at)}"
  - Reason `<textarea>`: Zod min(10) max(1000)
  - Confirmation checkbox: "I understand this will immediately end {holder_name}'s edit session"
  - "Force unlock" button: disabled until reason valid AND checkbox checked
  - On success: close + toast "Lock released successfully."

- [ ] **GREEN** — All dialog tests pass

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

**Status: PARTIAL** (2026-04-18) — Foundation shipped (types, API client, useSectionLock hook, lock indicator in spec tab). Groups 5-10 deferred on backend unlock-request/respond endpoints.

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
