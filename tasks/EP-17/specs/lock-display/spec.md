# Spec: Lock Indicator Display (US-171)

## Scope

Visual representation of the active lock state — list-view badges and detail-page banners — driven by SSE real-time updates, with correct stale-state cleanup.

---

## US-171 — See Lock Indicator When Another User is Editing

### Scenario 1: Lock badge appears on list row when item becomes locked

WHEN a work item transitions to locked state (another user acquired the lock)  
AND the current user is on a list view that includes that item  
THEN the client receives a `lock_acquired` SSE event on `sse:work_item:{id}`  
AND the list row renders a `LockBadge` component: a small lock icon and the holder's initials (e.g., "MG" for Maria Garcia)  
AND the badge appears within 1 second of the SSE event (no page refresh required)  
AND the badge has `aria-label="Being edited by Maria Garcia"` for accessibility  
AND the badge meets the 48dp touch target requirement (bounding box, not the icon itself)

### Scenario 2: Lock badge tooltip shows holder details on hover/focus

WHEN a user hovers or focuses the `LockBadge` on a list row  
THEN a tooltip renders: "Maria Garcia is editing · Started 2 min ago"  
AND the elapsed time is computed client-side from `acquired_at` in the SSE payload  
AND the tooltip updates the elapsed time every 60 seconds while visible  
AND the tooltip is dismissible with Escape key

### Scenario 3: Lock banner appears on detail page when item is already locked on mount

WHEN a user navigates to the detail page of a work item that is currently locked  
THEN the client fetches `GET /api/v1/work-items/:id/lock` on page mount  
AND if the response is `200 OK` with an active lock, the `LockBanner` component is rendered at the top of the detail page  
AND the banner content is: "[Avatar] Maria Garcia is editing this item · Started 2 min ago"  
AND the banner includes a "Request unlock" button (enabled for non-holders, hidden for the lock holder)  
AND the "Edit" button in the page header is disabled with tooltip: "Maria Garcia is currently editing"  
AND the banner is visually distinct (amber/warning background) and does not obscure content (banner is above the content area, not overlaid)

### Scenario 4: Lock banner appears on detail page when lock is acquired during viewing

WHEN a user is on the detail page in view mode  
AND another user acquires the lock  
THEN the client receives a `lock_acquired` SSE event on `sse:work_item:{id}`  
AND the `LockBanner` is injected without a page reload  
AND the "Edit" button is disabled immediately  
AND the transition is smooth (no flash of layout shift)

### Scenario 5: Lock banner and badge disappear when lock is released

WHEN a lock is released (voluntarily, by force, or by TTL expiry)  
AND the current user is viewing the item (detail page or list)  
THEN the client receives a `lock_released` SSE event  
AND the `LockBanner` is removed from the detail page without a page reload  
AND the `LockBadge` is removed from the list row  
AND the "Edit" button is re-enabled  
AND if `expired: true` in the payload, a transient toast appears: "Lock released — item is now available to edit"

### Scenario 6: Lock holder sees their own lock state in edit mode

WHEN the current user holds the lock and is in edit mode  
THEN the "Edit" button is replaced with "Editing…" (active indicator)  
AND a subtle lock indicator shows in the editor header: "You are editing · Lock expires in 4:32"  
AND the countdown ticks down every second  
AND when the lock is extended via heartbeat, the countdown resets to 5:00  
AND if the countdown reaches 0:00 (heartbeat failure), the lock-loss recovery banner activates (see acquire-release spec Scenario 9)

### Scenario 7: Stale lock indicator cleanup on SSE reconnect

WHEN the SSE connection was interrupted and re-established  
THEN the client re-fetches `GET /api/v1/work-items/:id/lock` on SSE reconnect  
AND if the lock has expired during the disconnection, the `LockBanner` and `LockBadge` are removed  
AND if a different user now holds the lock, the indicators update to show the new holder  
AND the client does NOT rely on stale in-memory state from before the disconnection

### Scenario 8: List view renders initial lock state on mount

WHEN a user loads a list view  
THEN the list endpoint response includes a `lock` field per item: `{ holder: { id, display_name, initials, avatar_url }, acquired_at } | null`  
AND items with a non-null `lock` field render the `LockBadge` immediately (no second request needed)  
AND items with `lock: null` render no badge

### Scenario 9: Mobile — lock badge on mobile list view

WHEN the user views the list on a mobile viewport (<640px)  
THEN the `LockBadge` is rendered as a lock icon only (no initials) to preserve row density  
AND tapping the badge shows a bottom sheet with holder details and the "Request unlock" option  
AND the tap target is at least 48dp

---

## Non-functional Requirements

- `LockBadge` and `LockBanner` must render in under 100ms after SSE event reception.
- SSE channel: `sse:work_item:{id}` — subscribes on mount of detail page, unsubscribes on unmount.
- List view does not subscribe to per-item SSE channels. It receives lock state from the initial fetch and updates via the workspace-level SSE channel (if available) or on-focus re-fetch.
- Time display: show relative time ("2 min ago", "just now") using a shared `useRelativeTime` hook. Recompute every 30 seconds.
- Accessibility: all lock indicators must have `role="status"` and `aria-live="polite"` for screen reader announcements on state change.
- Lock holder initials are derived from `display_name`: first letter of first name + first letter of last name, uppercase. Fallback: first two letters of username.
