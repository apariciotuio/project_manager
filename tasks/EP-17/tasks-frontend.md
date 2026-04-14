# EP-17 Frontend Tasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `LockBadge`, `SeverityBadge` (for lock banners), `TypedConfirmDialog` (for force-release with reason composed in body), `HumanError` (for heartbeat failures + connection issues), semantic tokens, i18n `i18n/es/lock.ts`. Do not introduce local lock badges, raw color classes, or English strings. See `tasks/extensions.md#EP-19`.

## Progress Tracking

Update checkboxes after each step. Format: `[x] Step — note (YYYY-MM-DD)`.

---

## Group 0: Setup & Types

- [ ] Create `src/types/lock.ts`: `LockDTO`, `UnlockRequestDTO`, `LockStatus`, `LockSSEEvent`, `LockAcquiredEvent`, `LockReleasedEvent`, `LockForceReleasedEvent`, `UnlockRequestedEvent`
- [ ] Create `src/api/lock-api.ts`: typed API client functions for all 7 lock endpoints (acquire, release, heartbeat, request-unlock, respond-to-request, force-release, get-status)
- [ ] Extend `WorkItemListItem` type with optional `lock: LockSummaryDTO | null`
- [ ] **RED** — Write type tests (compile-time only: verify no `any`, strict null checks pass)

---

## Group 1: `useWorkItemLock` Hook

- [ ] **RED** — Write tests for `useWorkItemLock` using `@testing-library/react` and MSW for API mocking:
  - `test_acquires_lock_on_entering_edit_mode`
  - `test_starts_heartbeat_interval_after_acquire`
  - `test_releases_lock_on_unmount`
  - `test_stops_heartbeat_on_unmount`
  - `test_sets_lock_lost_on_heartbeat_404`
  - `test_sets_lock_lost_on_heartbeat_403`
  - `test_shows_connection_issue_toast_on_503_heartbeat`
  - `test_exposes_is_holder_true_when_lock_held`
  - `test_exposes_is_holder_false_when_lock_not_held`
  - `test_does_not_discard_unsaved_draft_on_lock_loss`
  - Triangulate: rapid mount/unmount, multiple heartbeat intervals, network failure on acquire

- [ ] Implement `src/hooks/useWorkItemLock.ts`
  - On enter edit mode: call `acquireLock()`, set `isHolder=true`, store lock in state
  - Start `setInterval` heartbeat every `LOCK_HEARTBEAT_INTERVAL_MS` (default 30000)
  - Heartbeat callback: call heartbeat API, update `expires_at` in state. On `404` or `403` → set `lockLost=true`, clear interval. On `503` → show toast (do not clear interval yet).
  - `useEffect` cleanup: `clearInterval(heartbeatRef.current)`, call `releaseLock()` if `isHolder && !lockLost`
  - Return: `{ lock, isHolder, lockLost, lockLostReason, acquireLock, releaseLock }`

- [ ] **GREEN** — All hook tests pass
- [ ] **REFACTOR** — No `any`, strict types, hook has no UI logic (pure state/side-effects)

---

## Group 2: `LockBadge` Component

- [ ] **RED** — Write component tests:
  - `test_renders_lock_icon_and_initials_on_desktop`
  - `test_renders_icon_only_on_mobile_viewport`
  - `test_shows_tooltip_with_holder_name_and_elapsed_on_hover`
  - `test_tooltip_updates_elapsed_time_every_60s`
  - `test_tooltip_dismissible_with_escape`
  - `test_aria_label_includes_holder_name`
  - `test_touch_target_meets_48dp`
  - `test_opens_unlock_request_dialog_on_mobile_tap`

- [ ] Implement `src/components/locks/LockBadge.tsx`
  - Props: `lock: LockSummaryDTO`, `workItemId: UUID`, `onRequestUnlock: () => void`
  - Lock icon (Heroicons `LockClosedIcon` or equivalent)
  - Initials derived from `display_name`: first letters of first and last name, fallback first two chars of username
  - Mobile (`<640px`): icon only, tap triggers `onRequestUnlock`
  - Desktop: icon + initials, hover/focus shows `Tooltip` component
  - `aria-label="Being edited by {display_name}"`
  - Wrapping div: `min-h-[48px] min-w-[48px]` (touch target)
  - `role="status"` `aria-live="polite"`

- [ ] **GREEN** — All badge tests pass

---

## Group 3: `LockBanner` Component

- [ ] **RED** — Write component tests:
  - `test_renders_holder_avatar_name_and_elapsed_time`
  - `test_renders_request_unlock_button_for_non_holder`
  - `test_hides_request_unlock_button_for_holder`
  - `test_edit_button_is_disabled_when_banner_shown`
  - `test_updates_on_lock_acquired_sse_event`
  - `test_removes_on_lock_released_sse_event`
  - `test_shows_transient_toast_on_lock_released_with_expired_true`
  - `test_amber_background_applied`
  - `test_does_not_overlay_content`
  - `test_renders_on_mobile_375px_without_horizontal_scroll`

- [ ] Implement `src/components/locks/LockBanner.tsx`
  - Props: `lock: LockDTO | null`, `workItemId: UUID`, `isHolder: boolean`, `onRequestUnlock: () => void`
  - Amber/warning background (`bg-amber-50 border-amber-200`)
  - Content: `[Avatar] {display_name} is editing this item · Started {relativeTime(acquired_at)}`
  - "Request unlock" button: visible when `lock !== null && !isHolder`
  - Elapsed time via `useRelativeTime` hook (recomputes every 30s)
  - Position: above content area, not overlaid (not `position: fixed` / `position: absolute`)
  - `role="status"` `aria-live="polite"`

- [ ] **GREEN** — All banner tests pass

---

## Group 4: `useRelativeTime` Hook (shared utility)

- [ ] **RED** — Write tests:
  - `test_returns_just_now_for_less_than_1_minute`
  - `test_returns_minutes_ago`
  - `test_updates_on_30s_interval`
  - `test_clears_interval_on_unmount`

- [ ] Implement `src/hooks/useRelativeTime.ts`
  - Takes `timestamp: string | Date`
  - Returns `string` (e.g., "just now", "2 min ago", "1 hour ago")
  - Updates every 30 seconds via `setInterval`
  - Clears interval on unmount

- [ ] **GREEN** — Tests pass

---

## Group 5: `UnlockRequestDialog` Component

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

## Group 6: `HolderResponsePanel` Component

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

## Group 7: `ForceReleaseDialog` Component (Admin)

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

## Group 8: Lock Integration in Detail Page Edit Flow

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

## Group 9: Lock Badges in List View

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

## Group 10: Lock-Loss Recovery UX

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

- [ ] Verify all interactive lock elements meet 48dp touch target (`min-h-[48px] min-w-[48px]`)
- [ ] Verify all icon-only buttons have `aria-label`
- [ ] Verify `LockBanner` and `LockBadge` use `role="status"` and `aria-live="polite"`
- [ ] Verify `HolderResponsePanel` uses `role="alertdialog"`
- [ ] Verify keyboard navigation works for all dialogs (Tab, Shift+Tab, Escape, Enter)
- [ ] Verify no layout shift (CLS) on SSE-driven lock state transitions
- [ ] Test on 375px viewport: no horizontal scroll on any lock UI

---

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
