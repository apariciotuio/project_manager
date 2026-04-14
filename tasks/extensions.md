# Extensions to Existing Epics

New requirements that extend existing epics rather than creating new ones. Each extension must be applied to the epic's `proposal.md`, `design.md`, `tasks-backend.md`, and `tasks-frontend.md` during the next planning pass.

---

## EP-01 (Core Model) — Hierarchy column

**Triggered by**: New requirement #5 (Project → Milestone → Epic → Story hierarchy), EP-14

**Changes**:
- Add `parent_work_item_id UUID REFERENCES work_items(id) ON DELETE RESTRICT` to `work_items` table
- Add `parent_path` materialized path column for O(1) ancestor queries
- Extend `type` enum values: add `milestone`, `story`
- Add `HierarchyValidator` pure function for type-parent compatibility rules
- Add index `idx_work_items_parent` for child lookup

**Affected stories**: US-010 (model creation), US-011 (state machine — milestones may have different transition rules)

---

## EP-01 (Core Model) — Attachment count

**Triggered by**: New requirement #9 (attachments), EP-16

**Changes**:
- Add denormalized `attachment_count INTEGER NOT NULL DEFAULT 0` on `work_items` (updated via trigger or service from EP-16)
- Used by list view to show paperclip icon without joining `attachments`

---

## EP-03 (Clarification + Conversation) — Chatbot Split-View UX

**Triggered by**: New requirement #10 (chatbot on left, task on right)

**Changes to `tasks-frontend.md`**:
- **Work item detail page layout change**: split view — chat panel on left (collapsible), content on right
  - Desktop: 40/60 split, resizable divider
  - Mobile: tabs (Chat | Content) or bottom sheet for chat
- Chat panel: threaded conversation (EP-03 model), messages with inline "Apply this change" buttons
- Content panel: current specification + tasks, editable
- Sync state: when chat suggests a change, preview appears in content panel; accept applies patch
- Existing suggestion flow (EP-03 US-032) becomes the primary interaction model on the detail page

**New acceptance criteria**:
- WHEN a user opens a work item THEN chat panel is visible by default on desktop, collapsed on mobile
- WHEN chat suggests a change THEN content panel highlights the affected section
- WHEN user applies from chat THEN content updates without page reload

**No backend changes** — the existing EP-03 suggestion APIs already support this. The change is purely frontend UX.

---

## EP-09 (Listings + Dashboards) — My Items + Kanban

**Triggered by**: Requirements #1 (my items) and #6 (kanban board)

**Changes**:

### My Items filters (#1)
- Add quick filters to listings: `my-items`, `created-by-me`, `owned-by-me`, `assigned-to-me-for-review`
- Add saved filter presets at user level: users can save their frequent filter combinations
- Update `GET /api/v1/work-items` to support `?mine=true&mine_type=owner|creator|reviewer`

### Kanban board view (#6)
- Add new view: `GET /api/v1/work-items/kanban?project_id=X&group_by=state`
- Returns columns (one per state) with cards (work items)
- Frontend: drag-drop between columns triggers state transition (uses EP-01's transition endpoint)
- Transition errors (validation gates) surfaced inline on failed drop with revert animation
- Configurable: group by state (default), by owner, by tag (requires EP-15), by parent (requires EP-14)

**Affected stories**: US-090 (list), US-093 (pipeline — kanban is a richer variant)

---

## EP-10 (Admin) — Superadmin Capabilities + Tag Management + Puppet Config

**Triggered by**: Requirements #3, #4, #7, #13

**Changes**:

### Superadmin capability (#13)
- New capability: `superadmin` — cross-workspace + platform-level
- Powers:
  - Create users directly (bypass OAuth invitation)
  - Force-unlock any work item (EP-17)
  - Reset any user's OAuth state
  - View cross-workspace audit
- Superadmin is a flag on the `users` table, NOT a capability on `workspace_memberships` (it's global)
- Add `is_superadmin BOOLEAN NOT NULL DEFAULT FALSE` to `users`
- Bootstrap first superadmin via env variable / CLI command — NEVER via API

### Tag management (#7)
- New admin section for managing workspace tags (from EP-15)
- CRUD + merge + archive
- Audit events for every tag change

### Puppet integration config (#3, #4)
- New integration type: `puppet` (alongside `jira`)
- Same `integration_configs` table (Fernet-encrypted credentials)
- Additional config: Puppet API endpoint, API key, default document sources
- Documentation sources management: list of external URLs / paths to index
- Health check: ping Puppet API + last-sync timestamp

**New tasks-backend.md items**:
- Create user admin endpoint (superadmin only)
- Tag admin CRUD + merge operations
- Puppet integration config (delegate details to EP-13)
- Superadmin middleware / capability check

**New tasks-frontend.md items**:
- Admin user creation form (superadmin only)
- Tag management UI (list, rename, merge, archive)
- Puppet integration settings panel
- Cross-workspace audit viewer (superadmin only)

---

## EP-07 (Comments + Versions) — Inline Images in Comments

**Triggered by**: Requirement #9 (attachments), EP-16

**Changes**:
- Comments support inline images (paste from clipboard, drag-drop)
- Inline images are stored as attachments (EP-16) with `comment_id` set
- Comment rendering: markdown with embedded image refs, rendered inline
- Delete behavior: when a comment is deleted, its inline images are marked for cleanup

**No new tables** — reuses EP-16's `attachments` table.

---

## Summary Table

| Epic | Extension | Trigger | Priority |
|------|-----------|---------|----------|
| EP-01 | `parent_work_item_id` + materialized path | Req #5 (EP-14) | Must |
| EP-01 | `attachment_count` denormalized column | Req #9 (EP-16) | Should |
| EP-03 | Chatbot split-view layout (frontend only) | Req #10 | Must |
| EP-07 | Inline images in comments | Req #9 (EP-16) | Should |
| EP-09 | My items quick filters | Req #1 | Must |
| EP-09 | Kanban board view | Req #6 | Must |
| EP-10 | Superadmin + user creation | Req #13 | Must |
| EP-10 | Tag admin (from EP-15) | Req #7 | Must |
| EP-10 | Puppet integration config (from EP-13) | Req #3, #4 | Must |

---

## Next Steps

After approving these extensions and the 5 new epic proposals (EP-13 through EP-17), the next planning pass must:

1. Add detailed specs, design, tasks for each new epic (same pipeline as EP-00..EP-12)
2. Amend existing epics' design.md and tasks-*.md files with the extensions above
3. Update `tech_info.md` with new schema (tags, attachments, locks, hierarchy, Puppet configs)
4. Update `assumptions.md` — reverse Q8 (attachments ARE in scope now)
5. Re-run consistency review across the expanded plan (16 epics total)
6. Re-run specialist reviews if extensions change significant surface area
