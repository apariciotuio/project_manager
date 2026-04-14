# EP-12 Frontend Subtasks — Responsive, Security, Performance

> **Scope (2026-04-14, decisions_pending.md #27)**: Observability deferred. Drop Sentry frontend, product-event tracking, ops dashboard page, trace sampling. Keep `X-Correlation-ID` plumbing + showing the ID in error UI for support handoff. Below is rewritten — obsolete sections are removed.

**Stack**: Next.js 14+ (App Router), TypeScript strict, Tailwind CSS
**Note**: Layout primitives (Group 1) must be built before any other epic's frontend work begins. All other epics reuse these components.

---

## API Contract / Integration Points

| Feature | Backend endpoint / mechanism |
|---|---|
| Correlation ID | `X-Correlation-ID` request header; set per request in API client |
| CSRF token | `X-CSRF-Token` request header; auto-attached for state-changing methods |
| Job progress | `GET /api/v1/jobs/{job_id}/progress` SSE stream |
| CSP violations | auto-reported by browser to `POST /api/v1/csp-report` |

---

## Group 1 — Layout Primitives (build first)

These are shared across all epics. No other frontend epic should be unblocked until these exist.

### Tailwind Config
- [ ] [GREEN] Add to `tailwind.config.ts`: `theme.extend.minHeight['touch'] = '48px'` and `theme.extend.minWidth['touch'] = '48px'`
- [ ] [GREEN] Verify mobile-first breakpoint order in all new utility classes (no `sm:max-*` patterns)

### Acceptance Criteria — AppShell & Layout Primitives

WHEN viewport is <640px
THEN `AppShell` renders a bottom navigation bar with up to 5 items, each with 48dp tap targets and icon + label
AND no hamburger/side-drawer navigation is used (bottom bar is the primary nav)

WHEN viewport is ≥1024px
THEN `AppShell` renders a sidebar navigation

WHEN the virtual keyboard appears (input focused on mobile)
THEN the bottom navigation bar moves above the keyboard and the focused input is scrolled into view

WHEN `BottomSheet` is open
THEN focus is trapped inside the sheet (`role="dialog"`, `aria-modal="true"`)
AND the sheet can be dismissed by: swipe-down, Escape key, or backdrop tap
AND max-height is 75vh with internal scroll
AND the primary submit button is always visible without scrolling

WHEN `prefers-reduced-motion: reduce` is set
THEN `SkeletonLoader` shimmer animation is disabled; a static placeholder renders instead

WHEN `ErrorBoundary` catches a render error
THEN the page-level variant renders a full-page fallback with: error message, `correlation_id`, and "Go to inbox" link
AND the section-level variant renders an inline error + retry without unmounting the rest of the page

WHEN `DataTable` renders on a 375px viewport
THEN no horizontal overflow exists at the page level
AND the table scrolls horizontally within its container

### AppShell (`components/layout/AppShell.tsx`)
- [ ] [RED] Test: renders bottom navigation on viewport < 640px; renders sidebar on viewport >= 1024px
- [ ] [RED] Test: active nav item is highlighted
- [ ] [RED] Test: all nav links are keyboard-reachable
- [ ] [GREEN] Implement `AppShell` with responsive nav (bottom nav mobile / sidebar desktop)
- [ ] [GREEN] Bottom nav: 5 items max, 48dp tap targets, icon + label

### BottomSheet (`components/layout/BottomSheet.tsx`)
- [ ] [RED] Test: traps focus when open
- [ ] [RED] Test: max-height 75vh with internal scroll
- [ ] [RED] Test: dismisses on swipe-down, Escape key, and backdrop tap
- [ ] [RED] Test: submit button always visible without being scrolled off
- [ ] [GREEN] Implement `BottomSheet` component (mobile only; renders null on md+, or delegates to drawer)
- [ ] [GREEN] Accessible: `role="dialog"`, `aria-modal="true"`, focus trap

### StickyActionBar (`components/layout/StickyActionBar.tsx`)
- [ ] [RED] Test: stays visible when virtual keyboard appears (no overlap with keyboard)
- [ ] [GREEN] Implement `StickyActionBar` — fixed bottom bar for primary actions on mobile; renders inline on desktop

### DataTable (`components/layout/DataTable.tsx`)
- [ ] [RED] Test: no horizontal overflow on 375px viewport (horizontal scroll container wraps table)
- [ ] [RED] Test: full table visible on md+
- [ ] [GREEN] Implement `DataTable` with horizontal scroll container on mobile, full table on md+
- [ ] [GREEN] Sortable column headers, loading state prop, empty state prop

### EmptyState (`components/layout/EmptyState.tsx`)
- [ ] [GREEN] Implement `EmptyState` with props: `icon`, `heading`, `body`, `cta?` (optional action button)
- [ ] [GREEN] Variants: inbox-empty, search-no-results, filtered-no-results, no-access

### SkeletonLoader (`components/layout/SkeletonLoader.tsx`)
- [ ] [RED] Test: `prefers-reduced-motion` disables shimmer animation
- [ ] [GREEN] Implement `SkeletonLoader` with variants matching: inbox card, work item detail, table row, dashboard widget
- [ ] [GREEN] Shimmer animation via Tailwind `animate-pulse`; disabled via CSS media query

### ErrorBoundary (`components/layout/ErrorBoundary.tsx`)
- [ ] [RED] Test: catches render error and renders fallback UI instead of crashing
- [ ] [RED] Test: page-level variant shows full-page error with correlation_id and retry
- [ ] [RED] Test: section-level variant shows inline error with retry (does not unmount page)
- [ ] [GREEN] Implement page-level `ErrorBoundary` (wraps entire page)
- [ ] [GREEN] Implement section-level `ErrorBoundary` (wraps individual data sections)
- [ ] [GREEN] Both variants show `correlation_id` from last failed request in fallback UI

### InlineError (`components/layout/InlineError.tsx`)
- [ ] [GREEN] Implement `InlineError` for form field errors and section fetch errors
- [ ] [GREEN] Props: `message`, `onRetry?`

---

## Group 2 — API Client & Correlation ID

### Acceptance Criteria

WHEN any API request is made
THEN a new UUID v4 is generated per request (not per session) and sent as `X-Correlation-ID` header

WHEN a request fails (any error)
THEN the `correlation_id` from the response header is shown in the error UI as "Error reference: [correlation_id]"

WHEN a state-changing request (POST/PUT/PATCH/DELETE) is made
THEN `X-CSRF-Token` is automatically attached from the cookie or meta tag
AND GET requests do NOT include the CSRF token header

WHEN the API client receives HTTP 401
THEN all pending requests are aborted and the user is redirected to the login page

## Group 2 — API Client & Correlation ID

- [ ] [RED] Test: API client generates UUID v4 per request and sends `X-Correlation-ID` header
- [ ] [RED] Test: `correlation_id` is shown in error UI when a request fails
- [ ] [GREEN] Implement correlation ID generation in `lib/api-client.ts` (UUID generated per-request, not per session)
- [ ] [GREEN] Wire `correlation_id` into `ErrorBoundary` fallback and toast error messages
- [ ] [GREEN] Auto-attach `X-CSRF-Token` header for POST/PUT/PATCH/DELETE requests (read token from cookie or meta tag)

---

## Group 3 — Security: Content Security Policy

### Acceptance Criteria

WHEN any HTML page is served by Next.js
THEN the response includes a `Content-Security-Policy` header with at minimum:
- `default-src 'self'`
- `script-src 'self'` (no `unsafe-inline`, no `unsafe-eval`)
- `style-src 'self' 'unsafe-inline'` (documented Tailwind exception)
- `img-src 'self' data: https://lh3.googleusercontent.com`
- `frame-ancestors 'none'`
AND `X-Frame-Options: DENY` is set
AND `X-Content-Type-Options: nosniff` is set
AND `Referrer-Policy: strict-origin-when-cross-origin` is set

WHEN the CSP is violated by a browser
THEN the report is sent to `/api/v1/csp-report` (backend EP-12) via `report-uri` directive

## Group 3 — Security: Content Security Policy

- [ ] [RED] Test: all HTML responses include CSP header (check Next.js headers config)
- [ ] [GREEN] Configure CSP header in `next.config.ts` headers section
- [ ] [GREEN] Add `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin` headers in `next.config.ts`
- [ ] [GREEN] CSP `report-uri` pointing to `/api/v1/csp-report` (backend EP-12)

---

## Group 4 — Responsive: Inbox Mobile (EP-08 integration)

### Acceptance Criteria

WHEN the inbox renders on a 375px viewport
THEN no horizontal overflow exists at the page level
AND each inbox card has a minimum height of 48px (touch target compliance)
AND the primary action button (Open / Review) is visible without horizontal scroll

WHEN the inbox has more than 20 items
THEN a "Load more" button or infinite scroll is present at the bottom of the list
AND scroll position is preserved on back-navigation

## Group 4 — Responsive: Inbox Mobile (EP-08 integration)

- [ ] [RED] Test: inbox renders single-column cards on 375px viewport (no horizontal overflow)
- [ ] [RED] Test: inbox card tap target >= 48dp (min-h-[48px])
- [ ] [RED] Test: "Load more" visible when items > 20
- [ ] [GREEN] Apply mobile-first layout to inbox page and card component (EP-08 owns inbox; EP-12 provides the pattern)

---

## Group 5 — Responsive: Work Item Detail Mobile (EP-09 integration)

- [ ] [RED] Test: metadata accordion present on < 640px viewport
- [ ] [RED] Test: action bar is sticky at bottom on mobile
- [ ] [RED] Test: no horizontal overflow on 375px viewport
- [ ] [GREEN] Apply mobile-first layout to work item detail page (EP-09 owns detail; EP-12 provides StickyActionBar and accordion pattern)

---

## Group 6 — Responsive: Review Actions Mobile (EP-08 integration)

- [ ] [RED] Test: review action component renders `BottomSheet` on mobile (< 640px)
- [ ] [RED] Test: review action component renders side drawer on desktop (>= 640px)
- [ ] [RED] Test: submit button always visible in `BottomSheet` without internal scroll
- [ ] [GREEN] Wire review action component to `BottomSheet` on mobile (EP-08 owns review component; EP-12 provides BottomSheet)

---

## Group 7 — UI States (apply to all epics)

### Acceptance Criteria

WHEN any data-dependent view is fetching
THEN a `SkeletonLoader` matching the loaded layout renders immediately (no blank white flash)

WHEN a list API returns an empty array
THEN `EmptyState` renders with context-specific messaging:
- Inbox: "No pending items. You're up to date."
- Search (query ≥2 chars): "No results for [query]. Try different keywords."
- Filtered list: "No elements match the current filters." + "Clear filters" CTA
- Permission restriction: "You don't have access to view items here"

WHEN a fetch fails with 5xx or network timeout
THEN `InlineError` renders within the affected section with a "Retry" button
AND the rest of the page is not affected or unmounted

WHEN a form submission fails with HTTP 422
THEN each invalid field shows an inline error message below it with `aria-invalid="true"` and `aria-describedby` linking to the error
AND the form does NOT reset; user input is preserved
AND the submit button re-enables after displaying errors

## Group 7 — UI States (apply to all epics)

- [ ] [RED] Test: all data-dependent views show `SkeletonLoader` during fetch
- [ ] [RED] Test: `EmptyState` shown when API returns empty array
- [ ] [RED] Test: `InlineError` + Retry shown on 5xx or network timeout
- [ ] [RED] Test: form fields show inline error with `aria-invalid="true"` on 422 response field errors
- [ ] [GREEN] Apply SkeletonLoader to: inbox, work item list, work item detail, dashboard widgets, member list, audit log
- [ ] [GREEN] Apply EmptyState to: inbox, work item list, search results, dashboard, audit log
- [ ] [GREEN] Apply InlineError to: all form submissions, all section data fetches

---

## Group 8 — Observability (removed — decision #27)

Sentry FE, `@sentry/nextjs`, `sentry.client.config.ts`, `sentry.server.config.ts`, beforeSend hooks — **all out of scope**.

Retained: the `ErrorBoundary` still catches render errors and shows the `correlation_id` in the fallback UI (with copy-to-clipboard) so users can hand it to support. Errors are logged to the browser console only.

- [ ] [RED] Test: `ErrorBoundary` fallback shows the request `correlation_id` and exposes a copy button
- [ ] [GREEN] Implement `ErrorBoundary` with correlation-ID display

---

## Group 9 — Observability: Job Progress SSE (`hooks/useJobProgress.ts`)

### Acceptance Criteria

WHEN `useJobProgress(jobId)` mounts
THEN it connects to `GET /api/v1/jobs/{job_id}/progress` via `EventSource`
AND streams progress events as `{ status: 'running', percent: number, message: string }`

WHEN the SSE stream emits `event: done`
THEN the hook returns `{ status: 'complete', result }` and closes the `EventSource`

WHEN the SSE stream emits an error event
THEN the hook returns `{ status: 'error', message }` and closes the `EventSource`

WHEN the component using `useJobProgress` unmounts
THEN the `EventSource` is closed immediately (no resource leak)

WHEN the SSE connection drops unexpectedly
THEN the hook auto-reconnects up to 3 times with exponential backoff (1s, 2s, 4s)
AND after 3 failures, returns `{ status: 'error', message: 'Connection lost' }`

## Group 9 — Shared SSE Infrastructure & Job Progress

### Shared `useSSE` Hook (build before EP-03 and EP-08 SSE work)

All SSE consumers in this codebase (EP-03 conversation streaming, EP-08 notifications, EP-12 job progress) **must use this shared hook**. Duplicate `EventSource` implementations are not acceptable.

- [ ] [RED] Test `useSSE(url, onMessage, options?)`: connects to given URL via `EventSource`; calls `onMessage` per event; reconnects with exponential backoff on error (1s, 2s, 4s, max 30s); closes on unmount; accepts optional `reconnectOptions` to override backoff
- [ ] [GREEN] Implement `src/lib/sse.ts`: export `useSSE(url: string, onMessage: (event: MessageEvent) => void, options?: SSEOptions): { status: 'connecting' | 'open' | 'closed' | 'error' }` — single place where backoff logic lives; `EventSource.close()` on unmount guaranteed; supports optional `onBeforeReconnect` callback for token refresh before reconnect
- [ ] EP-03's `streamThread`, EP-08's `useSSENotifications`, and `useJobProgress` below must all delegate to `useSSE` — no direct `new EventSource(...)` calls outside `src/lib/sse.ts`

### Acceptance Criteria — useSSE

WHEN `useSSE` mounts with a valid URL
THEN an `EventSource` is opened to that URL
AND `onMessage` is called for each incoming event

WHEN the connection drops unexpectedly
THEN reconnection is attempted with exponential backoff: 1s, 2s, 4s, max 30s
AND `options.onBeforeReconnect` is called before each reconnect attempt (allows token refresh)

WHEN the component unmounts
THEN `EventSource.close()` is called immediately; no further events processed

### `useJobProgress` (builds on top of `useSSE`)

- [ ] [RED] Test: `useJobProgress(jobId)` connects to SSE stream and returns progress events
- [ ] [RED] Test: hook returns `{ status: 'complete', result }` on `event: done`
- [ ] [RED] Test: hook returns `{ status: 'error', message }` on error event
- [ ] [RED] Test: hook cleans up SSE connection on component unmount
- [ ] [GREEN] Implement `useJobProgress(jobId)` — wraps `useSSE` targeting `GET /api/v1/jobs/{job_id}/progress`
- [ ] [GREEN] Auto-reconnect on connection drop (max 3 retries via `useSSE` backoff)

---

## Group 10 — Performance

- [ ] Audit all images in codebase: replace with `next/image` where missing
- [ ] Audit all list views: add `react-window` virtual rendering for lists that may exceed 100 items (inbox, work item list, search results)
- [ ] [GREEN] Configure Lighthouse CI in pipeline: fail on LCP > 2.5s, CLS > 0.1, TBT > 300ms

---

## Group 11 — Accessibility

### Acceptance Criteria

WHEN any interactive element (button, link, toggle, checkbox, icon-button) renders
THEN its tap/click target area is at minimum 48x48dp
AND there is at least 8dp spacing between adjacent targets

WHEN any status badge renders
THEN an `aria-label` or accompanying text label provides equivalent meaning (not color alone)

WHEN any modal or `BottomSheet` opens
THEN focus is trapped inside until dismissed
AND Tab navigation cycles within the dialog only
AND Escape closes the dialog

WHEN a form field shows a validation error
THEN `aria-invalid="true"` is set on the field
AND the error message element id is referenced via `aria-describedby`

WHEN dynamic content updates (new notification, status change)
THEN the relevant region has `aria-live="polite"` so screen readers announce the update

WHEN `axe-core` runs in CI
THEN zero violations with impact `critical` or `serious` are present; the pipeline fails on any violation

## Group 11 — Accessibility

- [ ] [RED] Test: all interactive elements reachable by Tab in DOM order
- [ ] [RED] Test: modal dialogs trap focus (verify with `BottomSheet` and side drawers)
- [ ] [RED] Test: status badges have text label, not color alone (e.g., "Approved" not just a green dot)
- [ ] [GREEN] Add `aria-label` to all icon buttons and non-descriptive interactive elements across all components
- [ ] [GREEN] Add `aria-live` region for dynamic content updates (notifications, status changes in EP-08)
- [ ] [GREEN] Verify focus indicators are visible on all interactive elements (no `outline: none` without replacement)
- [ ] Configure `axe-core` in CI: fail on violations with impact `critical` or `serious`

---

## Group 12 — Ops Dashboard Page (removed — decision #27)

Ops dashboard, queue-depth view, integration-health view — **all out of scope**. The corresponding backend endpoints are also out of scope.
