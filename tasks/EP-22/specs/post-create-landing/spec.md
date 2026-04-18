# Post-Create Landing Specs — EP-22

## US-220: Land on SplitView immediately after creation

### Overview

After a workspace member submits the creation form (`/items/new`), the system redirects them to the work item detail route (`/workspace/{slug}/items/{id}`). That route renders the new `WorkItemDetailLayout` (split view) — NOT the pre-existing tabs layout. The left panel hosts the chat (`ChatPanel`); the right panel hosts the type-specific specification preview (`SpecificationSectionsEditor`). The redirect target is unchanged from EP-02; only what that route renders is new.

Layout state-independence: SplitView is rendered regardless of the work item state (Draft, IN_CLARIFICATION, READY, IN_PROGRESS, DONE, BLOCKED, DISCARDED). See `specs/splitview-scope/spec.md` for the state-scope scenarios.

---

### Scenario: Successful creation redirects to SplitView on desktop

WHEN an authenticated user submits the creation form with a valid title and type
AND the backend returns HTTP 201 with the new work item id
THEN the frontend navigates to `/workspace/{slug}/items/{id}`
AND the page renders `WorkItemDetailLayout` (split view)
AND the left panel renders `ChatPanel` for the element thread
AND the right panel renders the type-specific `SpecificationSectionsEditor` in editable mode
AND the existing tabbed layout (Especificación / Clarificación / Tareas / ...) is NOT rendered

---

### Scenario: Successful creation redirects to SplitView on mobile

WHEN the viewport width is <768px
AND a user completes the creation flow
THEN the detail route renders `WorkItemDetailLayout` in its mobile mode (tab switcher Chat | Content)
AND the default active mobile tab is `chat` (so the primed message is immediately visible)

---

### Scenario: Layout visible before chat or sections have loaded

WHEN the detail route mounts
AND the work item data, thread data, or section data have not yet resolved
THEN the split view scaffold renders immediately
AND each panel shows its own loading skeleton independently (`ChatPanel` skeleton left, sections skeleton right)
AND no tabs are shown at any point during loading

---

### Scenario: Redirect target unchanged for EP-02 flows

WHEN the EP-02 pre-creation draft resume flow or the edit-modal flow saves a work item
AND the flow currently navigates to `/workspace/{slug}/items/{id}`
THEN no change to that navigation target is required
AND the destination route now renders `WorkItemDetailLayout`

---

### Scenario: Layout renders for an existing work item opened cold

WHEN a user directly navigates to `/workspace/{slug}/items/{id}` for an existing work item (not freshly created)
THEN the detail page renders `WorkItemDetailLayout` regardless of the item's state
AND the user sees chat-left + sections-right at every lifecycle stage

---

### Scenario: Chat panel collapsed per-item

WHEN the user clicks the chat-panel collapse control
THEN the chat panel is hidden and the content panel expands to full width
AND the collapsed state persists per (user, work_item_id) — see design.md "Collapse state persistence"
AND WHEN the user reloads the same item THEN the chat panel remains collapsed
AND WHEN the user opens a different work item THEN the chat panel uses its own stored state (or the default expanded)

---

### Scenario: Item not found

WHEN the detail route is hit with a work item id that does not exist (or the user lacks access)
THEN the backend returns 404
AND the page shows an error state (no split view rendered)
AND no chat thread is created
