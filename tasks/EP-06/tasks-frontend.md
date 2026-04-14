# EP-06 Frontend Tasks — Reviews, Validations & Flow to Ready

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `StateBadge` for review decisions (approved/rejected/changes_requested variants), `TypedConfirmDialog` for override-ready (min 10-char justification enforced in business logic, not UI), `HumanError`, semantic tokens, i18n `i18n/es/review.ts`. Validation checklist and review detail views remain feature-specific. See `tasks/extensions.md#EP-19`.

Tech stack: Next.js 14+ App Router, TypeScript strict, Tailwind CSS

Blocked by: EP-06 backend Phase 6 complete. EP-08 SSE infrastructure must exist for real-time review notifications. EP-19 catalog available.

---

## API Client Contract

```typescript
// src/lib/api/reviews.ts

export type ReviewStatus = 'pending' | 'closed' | 'cancelled';
export type ReviewDecision = 'approved' | 'rejected' | 'changes_requested';
export type ValidationStatusEnum = 'pending' | 'passed' | 'waived' | 'obsolete';

export interface ReviewRequest {
  id: string;
  work_item_id: string;
  version_id: string;
  reviewer_type: 'user' | 'team';
  reviewer_id: string | null;
  team_id: string | null;
  validation_rule_id: string | null;
  status: ReviewStatus;
  requested_by: string;
  requested_at: string;
  cancelled_at: string | null;
  version_outdated: boolean;
  requested_version: number;
  current_version: number;
  response: ReviewResponse | null;
}

export interface ReviewResponse {
  id: string;
  review_request_id: string;
  responder_id: string;
  decision: ReviewDecision;
  content: string | null;
  responded_at: string;
}

export interface ValidationRule {
  rule_id: string;
  label: string;
  status: ValidationStatusEnum;
  passed_at: string | null;
}

export interface ValidationChecklist {
  required: ValidationRule[];
  recommended: ValidationRule[];
}

// createReviewRequest: POST /api/v1/work-items/:id/review-requests
// listReviewRequests: GET /api/v1/work-items/:id/review-requests
// getReviewRequest: GET /api/v1/review-requests/:id
// cancelReviewRequest: DELETE /api/v1/review-requests/:id
// submitReviewResponse: POST /api/v1/review-requests/:id/response
// getValidations: GET /api/v1/work-items/:id/validations
// waiveValidation: POST /api/v1/work-items/:id/validations/:rule_id/waive
// transitionToReady: POST /api/v1/work-items/:id/transition (body: { target_state: 'ready', override?, override_justification? })
```

---

## Group 1 — API Client Layer

### Acceptance Criteria

WHEN `createReviewRequest` returns 403
THEN error is typed as `{ code: 'FORBIDDEN' }`

WHEN `getReviewRequest` returns a review with `version_outdated=true`
THEN the `ReviewRequest` object has `version_outdated: true`, `requested_version: N`, `current_version: M`

WHEN `submitReviewResponse` returns 409
THEN error is typed as `{ code: 'REVIEW_ALREADY_CLOSED' }`

WHEN `submitReviewResponse` returns 422 (missing content)
THEN error includes field-level detail `{ field: 'content', message: '...' }`

WHEN `transitionToReady` returns 422 `READY_GATE_BLOCKED`
THEN error has `details.blocking_rules: Array<{ rule_id: string; label: string; status: string }>`

Blocked by: EP-06 backend Phase 6 complete

- [ ] 1.1 [RED] Test `createReviewRequest`: maps 201→`ReviewRequest`; 403→`FORBIDDEN`; 422→validation error
- [ ] 1.2 [RED] Test `getReviewRequest`: maps `version_outdated=true` correctly; `response` null vs present
- [ ] 1.3 [RED] Test `submitReviewResponse`: 200→`ReviewResponse`; 403→`FORBIDDEN`; 409→`REVIEW_ALREADY_CLOSED`; 422→content required
- [ ] 1.4 [RED] Test `transitionToReady`: 200→success; 422 `READY_GATE_BLOCKED`→`blocking_rules` extracted; 422 missing justification; 403
- [ ] 1.5 [GREEN] Implement `src/lib/api/reviews.ts` with full TypeScript types

---

## Group 2 — Hooks

### Acceptance Criteria

WHEN `useCreateReview` succeeds
THEN both the review list cache and the work item state cache are invalidated (work item may have transitioned to `in_review`)

WHEN `useSubmitReview` succeeds
THEN review request detail cache and work item state cache are invalidated

WHEN `useValidations.waive()` succeeds
THEN checklist cache is invalidated; pending count re-renders

WHEN `useTransitionToReady` receives `READY_GATE_BLOCKED`
THEN it surfaces `blockingRules: ValidationRule[]` as a dedicated field on the error result (not just `error.message`)
AND the hook exposes a `triggerOverride(justification)` function that re-sends with `override=true`

Blocked by: Group 1 complete

- [ ] 2.1 [RED] Test `useReviewRequests(workItemId)`: fetches list, returns `{ requests, isLoading, error }`
- [ ] 2.2 [GREEN] Implement `src/hooks/useReviewRequests.ts`
- [ ] 2.3 [RED] Test `useCreateReview(workItemId)`: submits, invalidates review list and work item state on success
- [ ] 2.4 [GREEN] Implement `src/hooks/useCreateReview.ts`
- [ ] 2.5 [RED] Test `useSubmitReview(reviewRequestId)`: submits response, invalidates review request and work item state
- [ ] 2.6 [GREEN] Implement `src/hooks/useSubmitReview.ts`
- [ ] 2.7 [RED] Test `useValidations(workItemId)`: fetches checklist; `waive` mutation invalidates checklist
- [ ] 2.8 [GREEN] Implement `src/hooks/useValidations.ts`
- [ ] 2.9 [RED] Test `useTransitionToReady(workItemId)`: success invalidates work item; `READY_GATE_BLOCKED` returns structured error with `blocking_rules`; override path sends `override=true`
- [ ] 2.10 [GREEN] Implement `src/hooks/useTransitionToReady.ts`

---

## Group 3 — Review Request Components

### Acceptance Criteria

**RequestReviewDialog**

WHEN `reviewer_type=user` is selected
THEN user search input is visible; team dropdown is hidden

WHEN `reviewer_type=team` is selected
THEN team dropdown is visible; user search input is hidden

WHEN submit returns 403
THEN inline error "Only the owner can request reviews" shown inside dialog (not a toast)

**ReviewRequestCard**

WHEN `request.version_outdated = true`
THEN a yellow banner renders with text: "Review requested on version N — the item has since been updated to version M"
AND reviewer can still see the Submit Response flow (not blocked)

WHEN `request.status = 'pending'` and `currentUserId === request.requested_by`
THEN Cancel button is visible; clicking calls `onCancel`

WHEN `request.status = 'closed'`
THEN the response decision chip (Approved/Rejected/Changes Requested) renders with correct color

Blocked by: Group 2 complete

### RequestReviewDialog

Props:
```typescript
interface RequestReviewDialogProps {
  workItemId: string;
  open: boolean;
  onSuccess: (request: ReviewRequest) => void;
  onClose: () => void;
}
```

- [ ] 3.1 [RED] Test: reviewer type toggle (user vs team); user selection shows user search input; team selection shows team dropdown; `validation_rule_id` optional select; submit calls `createReviewRequest`; success closes and calls `onSuccess`
- [ ] 3.2 [GREEN] Implement `src/components/reviews/RequestReviewDialog.tsx`

### ReviewRequestCard

Props:
```typescript
interface ReviewRequestCardProps {
  request: ReviewRequest;
  currentUserId: string;
  onCancel: (id: string) => void;
}
```

- [ ] 3.3 [RED] Test: shows reviewer name/team, status badge, requested date; `version_outdated=true` renders yellow warning banner "Review requested on an older version"; pending + current user is requester → shows Cancel button; closed shows response decision chip
- [ ] 3.4 [GREEN] Implement `src/components/reviews/ReviewRequestCard.tsx`

### ReviewRequestList

- [ ] 3.5 [RED] Test: empty state "No reviews requested yet"; loading skeleton; maps requests to `ReviewRequestCard`
- [ ] 3.6 [GREEN] Implement `src/components/reviews/ReviewRequestList.tsx`

---

## Group 4 — Review Response Component

### Acceptance Criteria

**SubmitReviewPanel**

WHEN `currentUserId` is not the `reviewer_id` (for `reviewer_type='user'`) AND not a member of the reviewer team (for `reviewer_type='team'`)
THEN component renders nothing (returns null — authorization is frontend-enforced here, backend enforces authoritatively)

WHEN `decision = 'approved'`
THEN content textarea is hidden; submit button label is "Approve"

WHEN `decision = 'rejected'` or `'changes_requested'`
THEN content textarea is required and visible; submit disabled until content is non-empty

WHEN server returns 409 `REVIEW_ALREADY_CLOSED`
THEN inline error: "This review has already been submitted"
AND radio group is disabled

Blocked by: Group 2 complete

### SubmitReviewPanel

Props:
```typescript
interface SubmitReviewPanelProps {
  reviewRequest: ReviewRequest;
  currentUserId: string;
  onSuccess: () => void;
}
```

- [ ] 4.1 [RED] Test: only renders for assigned reviewer; decision radio group (approve / request changes / reject); content textarea shown and required when decision != approved; approve hides content; submit calls `submitReviewResponse`; 409 shows "Review already submitted"
- [ ] 4.2 [GREEN] Implement `src/components/reviews/SubmitReviewPanel.tsx`
- [ ] 4.3 [RED] Test: approved decision shows green confirmation; rejected shows red; changes_requested shows orange
- [ ] 4.4 [GREEN] Implement decision color mapping in `SubmitReviewPanel`

---

## Group 5 — Validation Checklist

### Acceptance Criteria

**ValidationChecklist**

WHEN a required rule has `status = 'pending'`
THEN row renders with a red/gray indicator; no Waive button

WHEN a recommended rule has `status = 'pending'` and `isOwner = true`
THEN Waive button is visible; clicking shows confirmation dialog with rule label before calling `waiveValidation`

WHEN a rule has `status = 'passed'`
THEN green check icon and `passed_at` date displayed

WHEN a rule has `status = 'waived'`
THEN waived badge with `waived_by` name displayed; Waive button hidden

WHEN a rule has `status = 'obsolete'`
THEN row is visually dimmed; no action available

Blocked by: Group 2 complete

### ValidationChecklist component

Props:
```typescript
interface ValidationChecklistProps {
  workItemId: string;
  isOwner: boolean;
}
```

- [ ] 5.1 [RED] Test: required rules section renders as blocking gate (red/green indicator); recommended rules render with lighter styling; `passed` rule shows green check + date; `waived` shows waived badge; `pending` shows gray circle; loading skeleton
- [ ] 5.2 [GREEN] Implement `src/components/reviews/ValidationChecklist.tsx`
- [ ] 5.3 [RED] Test: recommended rule `status=pending` + `isOwner=true` → shows "Waive" button; clicking triggers confirmation dialog before calling `waiveValidation`; required rule → no waive button
- [ ] 5.4 [GREEN] Implement waive flow in `ValidationChecklist`

---

## Group 6 — Ready Gate & Transition

### Acceptance Criteria

**ReadyGatePanel**

WHEN all required rules are `passed`
THEN "Mark as Ready" button is enabled

WHEN any required rule is `pending`
THEN button is disabled; tooltip lists blocking rule labels

WHEN `isOwner = false`
THEN no button rendered at all

**ReadyTransitionButton**

WHEN `transitionToReady` returns 422 `READY_GATE_BLOCKED`
THEN blocking rules are rendered in an error panel below the button (not just a toast)
AND an "Override" link appears that opens `OverrideReadyDialog`

WHEN `transitionToReady` succeeds
THEN "Item is now Ready" toast shown; work item state cache invalidated; button replaced with a "Ready" state indicator

**OverrideReadyDialog**

WHEN justification textarea has fewer than 10 characters
THEN submit button is disabled

WHEN confirmation checkbox is not checked
THEN submit button is disabled

WHEN both fields are valid and submit is clicked
THEN `onConfirm(justification)` is called with the justification string
AND dialog closes

WHEN Cancel is clicked
THEN `onClose()` is called; no submit occurs; dialog closes without mutation

Blocked by: Groups 3–5 complete

### ReadyGatePanel

Props:
```typescript
interface ReadyGatePanelProps {
  workItemId: string;
  isOwner: boolean;
  currentState: string;
}
```

- [ ] 6.1 [RED] Test: all required rules passed → "Mark as Ready" button enabled; any required pending → button disabled with tooltip listing blocking rules; non-owner → no button shown
- [ ] 6.2 [GREEN] Implement `src/components/reviews/ReadyGatePanel.tsx`

### ReadyTransitionButton

- [ ] 6.3 [RED] Test: click calls `transitionToReady`; 422 `READY_GATE_BLOCKED` shows blocking rules in error panel (not just a toast); success shows "Item is now Ready" toast and invalidates work item state
- [ ] 6.4 [GREEN] Implement `src/components/reviews/ReadyTransitionButton.tsx`

### OverrideReadyDialog

Props:
```typescript
interface OverrideReadyDialogProps {
  blockingRules: ValidationRule[];
  open: boolean;
  onConfirm: (justification: string) => void;
  onClose: () => void;
}
```

- [ ] 6.5 [RED] Test: shows list of blocking rules being bypassed; justification textarea required (min 10 chars); confirmation checkbox required; submit calls `onConfirm` with justification; cancel closes without submitting
- [ ] 6.6 [GREEN] Implement `src/components/reviews/OverrideReadyDialog.tsx`
- [ ] 6.7 [RED] Test: `ReadyTransitionButton` on 422 gate blocked shows "Override" link that opens `OverrideReadyDialog`
- [ ] 6.8 [GREEN] Wire `OverrideReadyDialog` into `ReadyTransitionButton`

---

## Group 7 — Page Integration

Blocked by: Groups 3–6 complete

### Reviews tab on Work Item Detail page

- [ ] 7.1 [RED] Test: work item detail page has "Reviews" tab showing `ReviewRequestList` + `ValidationChecklist` + `ReadyGatePanel`
- [ ] 7.2 [GREEN] Create `src/app/(workspace)/items/[id]/reviews/page.tsx` (or extend tab layout)
- [ ] 7.3 [RED] Test: reviewer visiting item → sees `SubmitReviewPanel` for their pending request at top of reviews tab
  - Visibility rule: review is shown to user if `(reviewer_type='user' AND reviewer_id=currentUserId)` OR `(reviewer_type='team' AND currentUserId IN team.members)`
  - WHEN a review is assigned to a team of which the user is member THEN the review appears in the user's pending reviews (not just direct-assigned reviews)
- [ ] 7.4 [GREEN] Wire reviewer view in reviews page; pass `currentUserTeams: string[]` to `SubmitReviewPanel` for team-membership check
- [ ] 7.5 [RED] Test: real-time update — incoming SSE `notification_created` event with `subject_type=review` triggers `useReviewRequests` refetch without page reload
- [ ] 7.6 [GREEN] Wire SSE listener (from EP-08 `useNotifications`) to invalidate review cache on relevant notification events

---

## Group 8 — States & Responsive

- [ ] 8.1 Mobile: `RequestReviewDialog` renders as full-screen sheet on mobile breakpoints
- [ ] 8.2 [RED] Test: loading skeleton for validation checklist renders correct number of rule placeholders
- [ ] 8.3 [GREEN] Implement `ValidationChecklistSkeleton`
- [ ] 8.4 [RED] Test: error state on failed checklist fetch shows retry
- [ ] 8.5 [GREEN] Implement error state in `ValidationChecklist`
