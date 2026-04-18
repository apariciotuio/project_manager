# SplitView Scope Specs — EP-22

## US-225: SplitView available in all states; Clarificación tab removed

### Overview

Decision #4 (closed): the "Clarificación" tab is retired. Chat lives permanently in the left panel of `WorkItemDetailLayout` regardless of the work item's state. Decision #5 (closed): SplitView renders in **every** state (Draft, IN_CLARIFICATION, READY, IN_PROGRESS, DONE, BLOCKED, DISCARDED). Users can collapse the chat panel per-item for a content-only view.

---

### Scenario: Clarificación tab removed for Draft items

WHEN a user opens a work item in `Draft` state
THEN the detail page renders `WorkItemDetailLayout`
AND no tab named "Clarificación" is rendered anywhere on the page
AND no `<ClarificationTab>` component is mounted
AND the chat is always accessible via the left panel (desktop) or the Chat mobile tab

---

### Scenario: Clarificación tab removed for IN_CLARIFICATION items

WHEN a user opens a work item in `IN_CLARIFICATION` state
THEN the detail page renders `WorkItemDetailLayout`
AND no "Clarificación" tab is rendered
AND the chat left panel is the sole clarification surface

---

### Scenario: Clarificación tab removed for READY items

WHEN a user opens a work item in `READY` state
THEN the detail page renders `WorkItemDetailLayout`
AND no "Clarificación" tab is rendered

---

### Scenario: Clarificación tab removed for IN_PROGRESS items

WHEN a user opens a work item in `IN_PROGRESS` state
THEN the detail page renders `WorkItemDetailLayout`
AND no "Clarificación" tab is rendered

---

### Scenario: Clarificación tab removed for DONE items

WHEN a user opens a work item in `DONE` state
THEN the detail page renders `WorkItemDetailLayout`
AND no "Clarificación" tab is rendered
AND the chat remains available (read-only Dundun history accessible, user can still send messages — Dundun decides if it responds)

---

### Scenario: Clarificación tab removed for BLOCKED and DISCARDED items

WHEN a user opens a work item in `BLOCKED` or `DISCARDED` state
THEN the detail page renders `WorkItemDetailLayout`
AND no "Clarificación" tab is rendered

---

### Scenario: Collapse chat panel per-item

WHEN the user clicks the chat-panel collapse control
THEN the left panel hides
AND the content panel expands to full width
AND the collapsed state is persisted per (user, work_item_id) in localStorage under key `split-view:chat-collapsed:{work_item_id}`
AND the resize divider remains available for expanding back
AND WHEN the user reloads the same item THEN the chat panel stays collapsed
AND WHEN the user opens another work item THEN that item's own collapsed state is read (default: expanded)

---

### Scenario: Collapse is per-item, not per-user-global

WHEN user U collapses the chat on item A
AND user U opens item B
THEN item B's chat panel is expanded (default), not inheriting item A's collapsed state

---

### Scenario: Removal of the Clarificación tab retains no dead routes

WHEN the detail page is served
THEN no legacy `<TabsTrigger value="clarificacion">` is emitted
AND no `<TabsContent value="clarificacion">` is emitted
AND the `ClarificationTab` component file is removed from the codebase OR explicitly kept behind a not-imported dead-code deletion gate (decision: delete — keeps the tree clean)
AND any test fixtures that asserted the presence of the Clarificación tab are updated or deleted

---

### Scenario: Other tabs unaffected

WHEN the detail page is served in any state
THEN the other surfaces previously hosted inside tabs (Especificación, Tareas, Revisiones, Comentarios, Historial, Versiones, Sub-items, Auditoría, Adjuntos) are migrated into the right-panel content area
AND the user can navigate between those sub-surfaces in the right panel (e.g. via the existing tabs component scoped to the right panel)
AND the chat remains in the left panel throughout

---

### Scenario: Mobile retains a single clarification surface

WHEN the viewport is <768px
THEN `WorkItemDetailLayout` renders its mobile tab switcher with two tabs: `Chat` and `Content`
AND NO third "Clarificación" tab is rendered
AND the Chat tab hosts `ChatPanel`; the Content tab hosts the rest of the detail page (spec, tasks, reviews, etc.)
