# EP-08 Frontend Tasks — Teams, Assignments, Notifications & Inbox

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `TierBadge` (inbox tiers 1..4), `SeverityBadge` for notification severity, `OwnerAvatar`/`UserAvatar`, `RelativeTime`, `HumanError`, semantic tokens, i18n `i18n/es/inbox.ts` + `i18n/es/notifications.ts` + `i18n/es/team.ts`. Bell badge 99+ cap, SSE integration, team detail pages remain feature-specific. See `tasks/extensions.md#EP-19`.

Tech stack: Next.js 14+ App Router, TypeScript strict, Tailwind CSS

Blocked by: EP-08 backend Groups A–D controllers complete. SSE stream endpoint must exist before Group 5. EP-19 catalog available.

---

## API Client Contract

```typescript
// src/lib/api/teams.ts
export type TeamStatus = 'active' | 'deleted';
export type TeamRole = 'member' | 'lead';

export interface TeamMember {
  user_id: string;
  display_name: string;
  role: TeamRole;
  joined_at: string;
}

export interface Team {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  status: TeamStatus;
  can_receive_reviews: boolean;
  created_at: string;
  members: TeamMember[];
}

// src/lib/api/notifications.ts
export type NotificationState = 'unread' | 'read' | 'actioned';

export interface QuickAction {
  action: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  payload_schema: Record<string, unknown>;
}

export interface Notification {
  id: string;
  type: string;
  state: NotificationState;
  actor_id: string | null;
  subject_type: 'work_item' | 'review' | 'block' | 'team';
  subject_id: string;
  deeplink: string;
  quick_action: QuickAction | null;
  extra: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
  actioned_at: string | null;
}

// src/lib/api/inbox.ts
export interface InboxItem {
  item_id: string;
  item_type: string;
  item_title: string;
  owner_id: string;
  current_state: string;
  priority_tier: 1 | 2 | 3 | 4;
  tier_label: string;
  event_age: string;
  deeplink: string;
  quick_action: QuickAction | null;
  source: 'direct' | 'team';
  team_id: string | null;
}

export interface InboxData {
  tiers: Record<string, { label: string; items: InboxItem[]; count: number }>;
  total: number;
}

// Teams API:
// createTeam: POST /api/v1/teams
// listTeams: GET /api/v1/teams
// getTeam: GET /api/v1/teams/:id
// updateTeam: PATCH /api/v1/teams/:id
// deleteTeam: DELETE /api/v1/teams/:id
// addMember: POST /api/v1/teams/:id/members
// removeMember: DELETE /api/v1/teams/:id/members/:user_id
// updateMemberRole: PATCH /api/v1/teams/:id/members/:user_id/role

// Notifications API:
// listNotifications: GET /api/v1/notifications
// getUnreadCount: GET /api/v1/notifications/unread-count
// markRead: PATCH /api/v1/notifications/:id/read
// markAllRead: POST /api/v1/notifications/mark-all-read
// executeAction: POST /api/v1/notifications/:id/action
// getStreamToken: POST /api/v1/notifications/stream-token

// Inbox API:
// getInbox: GET /api/v1/inbox
// getInboxCount: GET /api/v1/inbox/count

// Assignments API:
// assignOwner: PATCH /api/v1/items/:id/owner
// getSuggestedReviewer: GET /api/v1/items/:id/suggested-reviewer
// getSuggestedOwner: GET /api/v1/items/:id/suggested-owner
// bulkAssign: POST /api/v1/items/bulk-assign
```

---

## Group 1 — API Client Layer

### Acceptance Criteria

WHEN `createTeam` returns 409
THEN error is typed as `{ code: 'TEAM_NAME_CONFLICT' }`

WHEN `addMember` or `removeMember` or `updateMemberRole` returns 409 `LAST_LEAD_REMOVAL`
THEN error is typed as `{ code: 'LAST_LEAD_REMOVAL' }`

WHEN `executeAction` returns 409
THEN error is typed as `{ code: 'STALE_ACTION' }`

WHEN `getInbox` response is received
THEN `InboxData.tiers` has keys `"1"`, `"2"`, `"3"`, `"4"` all present even if empty `{ items: [], count: 0 }`

WHEN `listNotifications` is called with `state` filter
THEN `?state=unread` is appended as query param (not in body)

Blocked by: EP-08 backend controllers complete

- [ ] 1.1 [RED] Test `createTeam`: 201→`Team`; duplicate name → 409 `TEAM_NAME_CONFLICT`
- [ ] 1.2 [RED] Test `addMember`: 200; last lead removal → 409 `LAST_LEAD_REMOVAL`
- [ ] 1.3 [RED] Test `listNotifications`: maps pagination correctly; state filter sent as query param
- [ ] 1.4 [RED] Test `executeAction`: 200→actioned; 409 `STALE_ACTION` mapped to error type
- [ ] 1.5 [RED] Test `getInbox`: maps tier structure to `InboxData`; `getInboxCount` returns per-tier + total
- [ ] 1.6 [GREEN] Implement `src/lib/api/teams.ts`, `src/lib/api/notifications.ts`, `src/lib/api/inbox.ts`, `src/lib/api/assignments.ts`

---

## Group 2 — Hooks

### Acceptance Criteria

WHEN `useNotifications.markRead(id)` is called
THEN notification `state` is optimistically set to `read` before server response
AND on server error, reverted to `unread`

WHEN `useNotifications.markAllRead()` is called
THEN all `unread` notifications in cache are optimistically set to `read`

WHEN `useUnreadCount` receives an `inbox_count_updated` SSE event
THEN count updates immediately without waiting for the 30s polling interval

WHEN `useInbox.refresh()` is called
THEN all four tiers are re-fetched simultaneously

Blocked by: Group 1 complete

- [ ] 2.1 [RED] Test `useTeams()`: fetches workspace teams; `createTeam` mutation invalidates list
- [ ] 2.2 [GREEN] Implement `src/hooks/useTeams.ts`
- [ ] 2.3 [RED] Test `useTeam(teamId)`: fetches detail with members; `addMember`, `removeMember`, `updateRole` each invalidate team detail
- [ ] 2.4 [GREEN] Implement `src/hooks/useTeam.ts`
- [ ] 2.5 [RED] Test `useNotifications()`: fetches list; `markRead` optimistically transitions state; `markAllRead` transitions all to read
- [ ] 2.6 [GREEN] Implement `src/hooks/useNotifications.ts`
- [ ] 2.7 [RED] Test `useUnreadCount()`: returns integer; SWR/query refetches every 30s as fallback; SSE event `inbox_count_updated` triggers immediate refetch
- [ ] 2.8 [GREEN] Implement `src/hooks/useUnreadCount.ts`
- [ ] 2.9 [RED] Test `useInbox()`: fetches inbox; `refresh` refetches; per-tier count badge accurate
- [ ] 2.10 [GREEN] Implement `src/hooks/useInbox.ts`

---

## Group 3 — SSE Client (Real-Time Notifications)

### Acceptance Criteria

See also: specs/notifications/spec.md (Real-Time Delivery section)

WHEN `useSSENotifications` mounts
THEN it fetches a stream-token from `/api/v1/notifications/stream-token`
AND opens `EventSource` with `?token=<token>` (EventSource cannot set Authorization header)

WHEN `notification_created` event is received
THEN the new notification is prepended to the `useNotifications` cache
AND `useUnreadCount` increments by 1 without a full refetch

WHEN `inbox_count_updated` event is received
THEN `useUnreadCount` cache is updated to the received `total` value immediately

WHEN the EventSource connection closes unexpectedly (error event)
THEN reconnect with exponential backoff: 1s, 2s, 4s, 8s ... up to max 30s
AND a new token is fetched before reconnecting (previous token may be expired)

WHEN stream-token fetch fails (401 or network error)
THEN no EventSource is opened; error logged; connection status = disconnected

WHEN the component unmounts
THEN `EventSource.close()` is called immediately; no lingering connection

WHEN `useSSENotifications` is mounted in `NotificationProvider` (root layout)
THEN only one global EventSource exists per session — no duplicate connections from multiple component mounts

Blocked by: EP-08 backend Group B5 (SSE endpoint) complete

- [ ] 3.1 [RED] Test `useSSENotifications()`: on `notification_created` event → prepends notification to `useNotifications` cache and increments unread count; on `notification_created` where `subject_type` is `review` or `block` → also invalidates `useInbox` cache; on `inbox_count_updated` → updates `useUnreadCount` cache; reconnects on disconnect; stops on unmount
- [ ] 3.2 [GREEN] Implement `src/hooks/useSSENotifications.ts`:
  - Fetches short-lived token from `/api/v1/notifications/stream-token`
  - **Use shared `useSSE(url, onMessage, { onBeforeReconnect })` hook from `src/lib/sse.ts` (owned by EP-12). Do not implement a standalone EventSource or custom backoff logic here.**
  - Pass `onBeforeReconnect` to fetch a fresh token before each reconnect attempt
  - Handles `notification_created` and `inbox_count_updated` event types via the `onMessage` callback
- [ ] 3.3 [RED] Test: token fetch fails → no EventSource opened, error logged; token expires mid-session → reconnects with new token
- [ ] 3.4 [GREEN] Mount `useSSENotifications` in root layout provider `src/providers/NotificationProvider.tsx` — single global connection per session

---

## Group 4 — Teams UI

### Acceptance Criteria

**TeamMemberList**

WHEN `currentUserRole = 'lead'` and member count > 1
THEN remove button is enabled for all non-self members

WHEN current user is the only lead
THEN remove button for that lead is disabled with tooltip: "Team needs at least one lead"

WHEN role dropdown selects a new role and the server returns 409 `LAST_LEAD_REMOVAL`
THEN inline error shown in the row: "Cannot demote the last lead"

**CreateTeamDialog**

WHEN server returns 409 `TEAM_NAME_CONFLICT`
THEN inline error rendered inside dialog on the name field: "Team name already exists"
AND dialog stays open

**AddMemberDialog**

WHEN user search returns a suspended user
THEN that user is shown in the dropdown but rendered as disabled with "(Suspended)" label
AND clicking a disabled entry does not add them to the selection

Blocked by: Group 2 complete

### TeamCard component

Props:
```typescript
interface TeamCardProps {
  team: Team;
  onEdit: (id: string) => void;
  onDelete: (id: string) => void;
}
```

- [ ] 4.1 [RED] Test: renders name, member count, `can_receive_reviews` badge; edit/delete buttons only for workspace admin; deleted team shown with strikethrough
- [ ] 4.2 [GREEN] Implement `src/components/teams/TeamCard.tsx`

### TeamMemberList component

Props:
```typescript
interface TeamMemberListProps {
  teamId: string;
  currentUserRole: TeamRole | null;
}
```

- [ ] 4.3 [RED] Test: renders member rows with avatar, name, role badge; lead badge distinct from member; remove button shown for leads/admin; role dropdown shown for leads; last lead → remove disabled with tooltip "Team needs at least one lead"
- [ ] 4.4 [GREEN] Implement `src/components/teams/TeamMemberList.tsx`

### CreateTeamDialog / EditTeamDialog

- [ ] 4.5 [RED] Test `CreateTeamDialog`: name required; `can_receive_reviews` toggle; submit calls `createTeam`; duplicate name shows inline 409 error "Team name already exists"
- [ ] 4.6 [GREEN] Implement `src/components/teams/CreateTeamDialog.tsx`
- [ ] 4.7 [RED] Test `EditTeamDialog`: pre-fills fields; submit calls `updateTeam`; soft delete shows confirmation "This will remove the team from review routing"
- [ ] 4.8 [GREEN] Implement `src/components/teams/EditTeamDialog.tsx`

### AddMemberDialog

Props:
```typescript
interface AddMemberDialogProps {
  teamId: string;
  existingMemberIds: string[];
  onSuccess: () => void;
  onClose: () => void;
}
```

- [ ] 4.9 [RED] Test: user search input (type-ahead); excludes existing members; role selector (member/lead); submit calls `addMember`; suspended users shown as disabled in dropdown
- [ ] 4.10 [GREEN] Implement `src/components/teams/AddMemberDialog.tsx`

### Teams Page

- [ ] 4.11 [RED] Test: `/workspace/teams` page renders `TeamCard` list; "Create team" button opens dialog; search/filter by name; empty state "No teams yet"
- [ ] 4.12 [GREEN] Create `src/app/(workspace)/teams/page.tsx`
- [ ] 4.13 [RED] Test: `/workspace/teams/[id]` renders team detail with `TeamMemberList`; breadcrumb navigation
- [ ] 4.14 [GREEN] Create `src/app/(workspace)/teams/[id]/page.tsx`

---

## Group 5 — Notifications UI

### Acceptance Criteria

**NotificationBell**

WHEN `unreadCount = 0`
THEN no badge rendered

WHEN `unreadCount = 100`
THEN badge displays "99+"

WHEN SSE `inbox_count_updated` event is received
THEN bell badge updates without user interaction

**NotificationItem**

WHEN `notification.state = 'unread'`
THEN item renders bold with a blue dot indicator

WHEN `notification.state = 'actioned'`
THEN checkmark indicator; action button hidden

WHEN `notification.quick_action` is present
THEN action button label matches `quick_action.action` (e.g., "Approve")

WHEN action button clicked
THEN `onExecuteAction(id, quick_action)` called; loading spinner shown on item

**NotificationDropdown**

WHEN item is hovered (desktop) or tapped (mobile)
THEN if `state = 'unread'`, `onMarkRead` is triggered optimistically

WHEN "Mark all read" is clicked
THEN all items in the list transition to `read` state optimistically; count badge resets to 0

Blocked by: Groups 2–3 complete

### NotificationBell component

Props:
```typescript
interface NotificationBellProps {
  unreadCount: number;
  onClick: () => void;
}
```

- [ ] 5.1 [RED] Test: renders bell icon; badge with count when `unreadCount > 0`; badge capped at "99+"; click calls `onClick`; real-time count updates via `useUnreadCount`
- [ ] 5.2 [GREEN] Implement `src/components/notifications/NotificationBell.tsx`

### NotificationItem component

Props:
```typescript
interface NotificationItemProps {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onExecuteAction: (id: string, action: QuickAction) => void;
}
```

- [ ] 5.3 [RED] Test: renders notification type icon; `summary` text; relative timestamp; unread items bold with blue dot; read items normal weight; `quick_action` present → renders action button; `actioned` state shows checkmark; clicking `onMarkRead` on unread item
- [ ] 5.4 [GREEN] Implement `src/components/notifications/NotificationItem.tsx`

### NotificationDropdown / Panel

- [ ] 5.5 [RED] Test: renders `NotificationItem` list; loading skeleton; empty state "You're all caught up"; "Mark all read" button; pagination "Load more"; transitions to read on hover (optimistic)
- [ ] 5.6 [GREEN] Implement `src/components/notifications/NotificationDropdown.tsx`

### Notifications Page

- [ ] 5.7 [RED] Test: `/notifications` full-page list; filter tabs (All / Unread / Actioned); `event_type` filter chip group; marks item as read on click; real-time new notifications prepended
- [ ] 5.8 [GREEN] Create `src/app/(workspace)/notifications/page.tsx`

---

## Group 6 — Inbox UI

### Acceptance Criteria

**InboxTierSection**

WHEN `items` array is empty
THEN "Nothing here" message renders; tier is still shown (collapsed or minimal)

WHEN `source = 'team'`
THEN team tag renders on the item row (e.g., "via Team Name")

WHEN `quick_action` is present on a Tier 1 item
THEN inline action button renders; clicking triggers `executeAction` with loading state
AND on success, item is removed from tier and tier count decrements
AND on 409 `STALE_ACTION`, toast error "This review has already been resolved" shown; item remains visible but action button disabled

**InboxPage**

WHEN `total = 0`
THEN full empty state renders: "Your inbox is clear" (not individual tier empties)

WHEN SSE `inbox_count_updated` event is received
THEN `useInbox.refresh()` is triggered lazily (not a full re-render; just invalidates cache for next interaction)

WHEN inbox fetch for one tier fails
THEN that tier renders an error state with retry; other tiers render normally

**InboxCountBadge**

WHEN total inbox count changes via SSE
THEN badge in sidebar nav updates without page reload

Blocked by: Groups 2–3 complete

### InboxTierSection component

Props:
```typescript
interface InboxTierSectionProps {
  tier: 1 | 2 | 3 | 4;
  label: string;
  items: InboxItem[];
  count: number;
}
```

- [ ] 6.1 [RED] Test: renders tier label with count badge; item rows with title, state chip, `event_age` relative time; `quick_action` present → inline action button; `source=team` shows team tag; empty tier shows "Nothing here" collapse; tier 1 has highest visual weight (red badge)
- [ ] 6.2 [GREEN] Implement `src/components/inbox/InboxTierSection.tsx`

### InboxPage

- [ ] 6.3 [RED] Test: `/inbox` renders all 4 tier sections; `total=0` shows full empty state "Your inbox is clear"; refresh button refetches all; real-time `inbox_count_updated` SSE event triggers refetch
- [ ] 6.4 [GREEN] Create `src/app/(workspace)/inbox/page.tsx`
- [ ] 6.5 [RED] Test: executing a `quick_action` from inbox — shows loading spinner on item, success removes item from tier, failure shows toast with retry
- [ ] 6.6 [GREEN] Implement quick action execution in `InboxTierSection` via `executeAction` + `useInbox` invalidation

### InboxCountBadge (nav sidebar)

- [ ] 6.7 [RED] Test: sidebar nav renders inbox link with total count badge; count from `useUnreadCount`; SSE `inbox_count_updated` updates badge without page reload
- [ ] 6.8 [GREEN] Implement `src/components/inbox/InboxCountBadge.tsx` and wire into nav sidebar

---

## Group 7 — Assignments UI

### Acceptance Criteria

**AssignOwnerButton**

WHEN user picker opens
THEN suggested owner (from `suggestedOwnerId`) appears first in the list with a "Suggested" label

WHEN a suspended user is present in the picker
THEN they are rendered as disabled (greyed, not selectable)

WHEN `assignOwner` is called and succeeds
THEN owner avatar and name update immediately (optimistic or on cache invalidation)

**ReviewerAssignmentSection**

WHEN "Get suggestion" is clicked and `getSuggestedReviewer` returns `null`
THEN inline message "No routing rule configured for this item type" shown

WHEN suggestion is returned
THEN reviewer field is pre-filled with the suggested user/team (user can still change it)

**BulkAssignDialog**

WHEN server returns 207
THEN per-item results table renders: green checkmark for success rows, red X for failed rows with error text

WHEN server returns 422 (suspended target)
THEN dialog shows single error: "Selected user is suspended and cannot receive assignments"

Blocked by: Group 1 complete

### AssignOwnerButton

Props:
```typescript
interface AssignOwnerButtonProps {
  itemId: string;
  currentOwnerId: string | null;
  suggestedOwnerId: string | null;
}
```

- [ ] 7.1 [RED] Test: renders current owner avatar + name; clicking opens user picker dropdown; suggested owner shown first with "Suggested" label; selecting calls `assignOwner`; suspended users disabled
- [ ] 7.2 [GREEN] Implement `src/components/assignments/AssignOwnerButton.tsx`

### ReviewerAssignmentSection (in EP-06 RequestReviewDialog)

- [ ] 7.3 [RED] Test: when selecting reviewer, "Get suggestion" button calls `getSuggestedReviewer`; suggestion pre-fills reviewer field; no suggestion shows "No routing rule configured"
- [ ] 7.4 [GREEN] Wire `getSuggestedReviewer` into EP-06 `RequestReviewDialog`

### BulkAssignDialog

Props:
```typescript
interface BulkAssignDialogProps {
  itemIds: string[];
  open: boolean;
  onSuccess: (results: { item_id: string; success: boolean; error?: string }[]) => void;
  onClose: () => void;
}
```

- [ ] 7.5 [RED] Test: user picker; submit calls `bulkAssign`; 207 partial failure shows per-item success/error rows; full success shows count "N items assigned"
- [ ] 7.6 [GREEN] Implement `src/components/assignments/BulkAssignDialog.tsx`

---

## Group 8 — States & Responsive

- [ ] 8.1 Mobile: notification dropdown renders as full-screen bottom sheet; inbox renders as flat list (tiers collapsed to accordions)
- [ ] 8.2 [RED] Test: notification bell loading skeleton renders bell outline during `getUnreadCount` fetch
- [ ] 8.3 [GREEN] Implement `NotificationBellSkeleton`
- [ ] 8.4 [RED] Test: SSE connection status indicator — "Live" green dot in notification panel when connected; "Reconnecting..." when disconnected
- [ ] 8.5 [GREEN] Implement SSE connection status indicator in `NotificationDropdown`
- [ ] 8.6 [RED] Test: inbox tier section loading skeleton renders 3 item placeholders per tier
- [ ] 8.7 [GREEN] Implement `InboxTierSkeleton`
- [ ] 8.8 [RED] Test: error state on inbox fetch shows retry; partial tier failure shows tier with error state while others render normally
- [ ] 8.9 [GREEN] Implement per-tier error states in `InboxPage`

---

## EP-08 FE Inbox Polish — Completed 2026-04-17

**Status: COMPLETED** (2026-04-17)

### Commit 1 — Inbox filter bar (feat(inbox): filter bar with unread / mentions / reviews tabs + search)
- [x] `InboxFilterBar`: tab-based filter (All / Unread / Mentions / Reviews) + free-text search input
- [x] `InboxFilterBarWithUrlSync`: URL-synced via useSearchParams + router.replace
- [x] Client-side search filters by summary/actor_name from extra field
- [x] Unread tab sends `only_unread=true` to API; Mentions/Reviews use type-filter client-side
- [x] `Sheet` UI primitive (Radix Dialog styled as right-side drawer) — `components/ui/sheet.tsx`
- [x] Inbox page wired: InboxFilterBarWithUrlSync above list, NotificationSheet stub included
- [x] Locale keys added: `workspace.inbox.filter.*`, `workspace.inbox.searchPlaceholder`, `workspace.inbox.sheet.*`, `workspace.inbox.{errorBanner,retry,prev,next,pageOf,markAllRead,onlyUnread}`, `workspace.notificationBell.{dnd,dndOff}` (en + es)
- [x] 5 filter-bar tests; existing inbox-page test updated (checkbox→tab change)

### Commit 2 — Notification sheet (feat(notifications): right-drawer sheet for action-required notifications)
- [x] `NotificationSheet`: summary, actor, created_at; "Mark actioned" button for quick_action notifications
- [x] PATCH `/notifications/{id}/actioned` on button click; calls `onMarkActioned` callback
- [x] Inbox page: rows without deeplink call `handleOpenSheet` instead of navigating
- [x] `NotificationBell`: adds `onOpenSheet` prop to `NotificationItem`; renders `NotificationSheet` sibling
- [x] `NotificationItem`: `onOpenSheet?: (notification) => void` prop added
- [x] 4 NotificationSheet tests: render, conditional button, PATCH happy path, onOpenSheet prop

### Commit 3 — markActioned + DND toggle (feat(notifications): mark-actioned + DND toggle)
- [x] `useUnreadCount` extended: `{paused}` option stops polling and skips fetches
- [x] `NotificationBell`: reads `localStorage('notifications.muted')` on mount; `toggleDnd` persists
- [x] DND button in popover header (`data-testid=dnd-toggle`, `data-dnd-active` attr); BellOff icon when active
- [x] `useNotifications` hook unchanged — markActioned available via `lib/api/notifications.ts` already
- [x] 4 DND tests: markActioned PATCH, localStorage persist, polling pause, persist across remounts

### EP-06 Gap — Version ID wiring (fix(reviews): wire real version_id from detail page)
- [x] `RequestReviewDialog`: `versionId: string | null` prop — null disables submit + shows "Generating first version…" hint
- [x] `ReviewsTab`: forwards `versionId` to `RequestReviewDialog`
- [x] Detail page: `useVersions(id)` on mount; `latestVersionId = versions[0]?.id ?? null` passed to `<ReviewsTab>`
- [x] Existing dialog tests updated to pass `versionId="v-1"` for submit-path tests
- [x] 2 new versionId tests: null disables + shows hint; real id in POST body
- [x] `workspace.itemDetail.reviews.requestDialog.versionPending` locale key added (en + es)

**Test count delta: +901 → 911 (+10 net new tests)**
