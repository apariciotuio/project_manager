# Spec: Responsive & Accessibility — US-120, US-121

## US-120 — Responsive use and critical mobile actions

### Breakpoints

| Token | Min width | Target devices |
|-------|-----------|----------------|
| `sm`  | 640px     | Large phones (landscape) |
| `md`  | 768px     | Tablets (portrait) |
| `lg`  | 1024px    | Tablets (landscape), small laptops |
| `xl`  | 1280px    | Desktop |

Mobile-first: default styles target <640px. Larger breakpoints layer on top.

---

### Scenario 1 — Inbox on mobile

WHEN a user opens the inbox on a viewport <640px
THEN the inbox list renders in a single-column stacked layout
AND each inbox card shows: title, status badge, assignee avatar, and relative timestamp
AND the primary action button (Open / Review) is visible without horizontal scroll
AND cards have a minimum touch target of 48x48dp

WHEN the user taps a card
THEN full-screen navigation to element detail occurs (no side panel)

WHEN the inbox has more than 20 items
THEN a "Load more" button or infinite scroll is present
AND the scroll position is preserved on back-navigation

---

### Scenario 2 — Element detail on mobile

WHEN a user opens element detail on a viewport <640px
THEN the metadata section (title, type, status, assignee) appears above the content area
AND the LLM summary/analysis is collapsible to save vertical space
AND the action bar (Approve / Request changes / Reject) is sticky at the bottom of the viewport
AND all action buttons meet the 48dp minimum touch target requirement

WHEN the element has attachments or linked Jira issues
THEN they are rendered in an accordion or collapsible section below the main content

---

### Scenario 3 — Review actions on mobile

WHEN a reviewer opens the review action drawer on mobile
THEN the drawer slides up from the bottom (bottom sheet pattern)
AND the drawer occupies at most 75% of viewport height
AND the reviewer can scroll inside the drawer without scrolling the background page
AND the submit button is always visible at the bottom of the drawer without scrolling

WHEN the reviewer submits a review action
THEN the bottom sheet dismisses
AND the element status updates in place without full-page reload

---

### Scenario 4 — Navigation on mobile

WHEN a user is on any page on mobile
THEN a persistent bottom navigation bar is visible with: Inbox, Search, Notifications, Profile
AND the top app bar shows page title and a contextual back arrow where applicable
AND hamburger/side-drawer navigation is NOT used (bottom bar is the primary nav)

WHEN the virtual keyboard appears (form input focused)
THEN the bottom navigation bar moves above the keyboard
AND the focused input is scrolled into view

---

### Scenario 5 — Touch targets and gestures

WHEN any interactive element (button, link, toggle, checkbox) is rendered
THEN its tap target area is at minimum 48x48dp regardless of visual size
AND tap targets have at least 8dp spacing between adjacent targets

WHEN a user long-presses a table row or card on mobile
THEN a context menu appears with the most common actions

---

### Scenario 6 — Viewport and overflow

WHEN any page loads on a mobile viewport
THEN no horizontal scroll exists at the page level
AND no content is clipped by viewport edges

WHEN a table with many columns is displayed on mobile
THEN the table scrolls horizontally within its container (not the full page)
AND sticky first-column is applied for context

---

## US-121 — Accessibility and UI states

### Scenario 7 — Loading states

WHEN any list, detail, or dashboard view is fetching data
THEN a skeleton screen matching the layout of the loaded content is displayed
AND the skeleton uses a shimmer/pulse animation at reduced motion if `prefers-reduced-motion` is set
AND no blank white flash appears between navigation transitions

WHEN a loading operation exceeds 3 seconds
THEN the skeleton remains visible and a subtle "Still loading..." text appears

WHEN a loading operation fails
THEN the error state (Scenario 9) replaces the skeleton immediately

---

### Scenario 8 — Empty states

WHEN a list view returns zero results
THEN a contextual empty state is shown with: icon, heading, explanatory text, and (where applicable) a primary CTA
AND the empty state message varies by context:
  - Inbox: "No pending items. You're up to date."
  - Search results: "No results for [query]. Try different keywords."
  - Element list with active filters: "No elements match the current filters." + Clear filters CTA

WHEN the empty state is due to a permission restriction
THEN the message says "You don't have access to view items here" — not a generic empty message

---

### Scenario 9 — Error states

WHEN a network request fails with a 5xx or network timeout
THEN the affected section shows an inline error banner: "Something went wrong. [Retry]"
AND the retry button re-triggers the failed request without full page reload
AND the rest of the page remains functional

WHEN a critical page-level error occurs (unhandled exception reaches ErrorBoundary)
THEN the full-page error fallback renders with: error message, correlation ID, and "Go to inbox" link
AND the error is reported to Sentry with the correlation ID attached

WHEN a form submission fails with a 422 validation error
THEN each invalid field shows an inline error message below the field
AND the form does not reset (user input is preserved)
AND the submit button re-enables after error display

---

### Scenario 10 — Keyboard and screen reader accessibility

WHEN a user navigates using keyboard only
THEN all interactive elements are reachable via Tab in logical DOM order
AND focus indicators are visible with minimum 3:1 contrast ratio against background
AND modal dialogs trap focus within until dismissed

WHEN a screen reader user reaches a status badge, icon button, or chart
THEN an `aria-label` or `aria-describedby` provides equivalent text
AND dynamic content updates (status changes, new notifications) are announced via `aria-live`

WHEN a form field has a validation error
THEN the error is associated via `aria-describedby` and `aria-invalid="true"`

---

### Scenario 11 — Color and contrast

WHEN any text is rendered
THEN body text meets WCAG AA contrast ratio (4.5:1 minimum)
AND large text (18px+ regular or 14px+ bold) meets 3:1 minimum

WHEN status is communicated by color alone (e.g., status badges)
THEN an additional visual indicator (icon or text label) accompanies the color

---

### Scenario 12 — Reduced motion

WHEN a user has `prefers-reduced-motion: reduce` set in their OS
THEN all CSS transitions and animations are disabled or replaced with instant transitions
AND skeleton shimmer animations are replaced with static placeholders
