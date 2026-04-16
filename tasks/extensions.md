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

---

## EP-19 (Design System) — Global frontend retrofit

**Triggered by**: EP-19 introduces shadcn/ui + semantic tokens + a shared domain catalog + ES tuteo i18n + a11y/size-limit gates. Every previously-planned frontend task file makes local decisions that must now defer to the catalog.

**Applies to**: every epic with frontend scope except **EP-12** (EP-12 is the provider of technical primitives; EP-19 builds on top — see "Amendments NOT required" below). Concretely: EP-00, EP-01, EP-02, EP-03, EP-04, EP-05, EP-06, EP-07, EP-08, EP-09, EP-10, EP-11, EP-13, EP-14, EP-15, EP-16, EP-17, EP-18.

### Common retrofit patches (apply to every listed epic's `tasks-frontend.md`)

1. **Preamble** — add at the top of `tasks-frontend.md`:
   > This epic follows **EP-19 (Design System & Frontend Foundations)**. Use catalog components from `components/system/*`, semantic tokens (`bg-state-*`, `bg-severity-*`, `bg-primary`, `bg-destructive`), i18n keys from `i18n/es/*`, and shared hooks. Do not introduce local badges, confirmation dialogs, plaintext reveals, command palettes, empty states, or raw Tailwind colors.

2. **Component substitutions** — remove local definitions; consume from EP-19 catalog:

| Epic | Local component → EP-19 replacement |
|---|---|
| EP-01 | `StateChip`/`DerivedStateBadge` → `StateBadge`; `TypeBadge` → `TypeBadge`; force-ready modal → `TypedConfirmDialog` (with min-char enforcement moved to business logic, not UI) |
| EP-02 | `TypeSelector` icon map → `TypeBadge` icons (shared); `DraftResumeBanner` kept local (feature-specific) |
| EP-03 | `GapPanel` severity colors → `SeverityBadge`; suggestion copy buttons → `CopyButton`; errors → `HumanError` |
| EP-04 | `CompletenessPanel` level badge → `LevelBadge`; `CompletenessBar` → shared; empty state → `EmptyStateWithCTA` |
| EP-05 | `TaskStatusBadge` → `StateBadge` (task variant in dictionary); `BlockedBadge` → `SeverityBadge` warning |
| EP-06 | Decision chips (approved/rejected/changes_requested) → `StateBadge` variants; override dialog → `TypedConfirmDialog` |
| EP-07 | Diff hunks → `DiffHunk`; version selector badge → `VersionChip`; timestamps → `RelativeTime`; image paste flow uses EP-16 integration (unchanged) |
| EP-08 | Tier labels → `TierBadge`; notification severity → `SeverityBadge`; 99+ badge stays on the bell (feature-specific) |
| EP-09 | Filter chips kept local (feature-specific); state colors → `StateBadge`; kanban badges → `StateBadge`/`TypeBadge`; search top bar uses `CommandPalette` |
| EP-10 | Admin confirmation dialogs → `TypedConfirmDialog`; rule-state chips → `StateBadge`; errors → `HumanError` |
| EP-11 | `JiraBadge` → shared; divergence banner uses `SeverityBadge` warning; export-row status → `StateBadge` |
| EP-13 | Top-bar search → `CommandPalette` contributes search results; doc-source status → `StateBadge`; Puppet outage → `HumanError` code `upstream_unavailable` |
| EP-14 | `RollupBadge` → shared; `TypeBadge` (milestone, story) from shared map; breadcrumb stays local (feature-specific) |
| EP-15 | `TagChip`/`TagChipList` → shared (including contrast computation); tag combobox stays feature-specific |
| EP-16 | Delete confirmation → `TypedConfirmDialog`; upload errors → `HumanError`; gallery empty state → `EmptyStateWithCTA` |
| EP-17 | `LockBadge` → shared; lock banner uses `SeverityBadge` warning; force-release dialog → `TypedConfirmDialog` with reason field composed into body; unlock request uses `CheckboxConfirmDialog` optional |
| EP-18 | MCP token plaintext reveal → `PlaintextReveal`; revoke confirmation → `TypedConfirmDialog`; rotate reuses `PlaintextReveal`; status chips → `StateBadge` |
| EP-00 | Login/workspace-picker adopts new typography + tokens; errors → `HumanError` |

3. **Tokens & typography** — replace every raw Tailwind color (`bg-blue-500`, `text-red-600`, etc.) with semantic tokens. Replace `text-3xl font-bold` and similar with `text-h1`/`text-display`. CI lint rules `no-raw-tailwind-color` and `no-raw-text-size` enforce.

4. **Copy & tone** — move every user-visible string to `apps/web/src/i18n/es/*.ts`. Replace English placeholders ("Save", "Cancel", "Are you sure?") with Spanish tuteo dictionary entries. `no-literal-user-strings` and `tone-jargon` lints enforce.

5. **Error UX** — replace ad-hoc error banners with `<HumanError code="..." correlationId={...} />`. Add any missing error codes to `i18n/es/errors.ts` in the same PR.

6. **Delete local component tests** — move component-level tests to EP-19. Keep integration tests in the feature epic.

7. **A11y + perf gates apply** — Lighthouse ≥ 95 and `size-limit` CI gates are now required on every PR under `apps/web/`.

### Retrofit execution order

Rolling PRs from smallest frontend surface to largest (matches EP-19 `tasks-frontend.md` Phase C):

EP-18 → EP-17 → EP-15 → EP-16 → EP-14 → EP-13 → EP-11 → EP-10 → EP-09 → EP-08 → EP-07 → EP-06 → EP-04 → EP-05 → EP-03 → EP-02 → EP-01 → EP-00

Each retrofit PR:
- Carries the checkbox tick in `tasks/EP-19/tasks-frontend.md#Phase-C`
- Updates the affected epic's `tasks-frontend.md` with adoption notes
- Passes all CI gates (lints, a11y, size-limit, Storybook build)

### Amendments NOT required

- **EP-12**: already owns layout primitives. No retrofit — EP-19 depends on EP-12, consumes its primitives, adds domain/style layer on top.
- **Backend-side of any epic**: EP-19 is frontend-only; backend tasks and design unaffected.

### What to update in each epic's `tasks-frontend.md`

Append this note (customized per epic) during the retrofit PR:

> **[EP-19 adoption]** This task file has been retrofitted to consume the shared design system. Local badges/dialogs/plaintext flows have been removed; see `tasks/EP-19/tasks-frontend.md#Phase-C` for the adoption checklist and `tasks/extensions.md#EP-19` for the substitution table.

---

## EP-00 (Auth) — OAuth state in Postgres, not Redis

**Triggered by**: M0 infra descope (Redis and MinIO removed 2026-04-15; cache/broker collapsed onto Postgres).

**Date**: 2026-04-15

**Changes**:
- New table `oauth_states(state PK, verifier, expires_at, created_at)` with index on `expires_at`. Alembic migration `006_create_oauth_states`.
- New domain interface `IOAuthStateRepository` (`create`, `consume`, `cleanup_expired`) and SQLAlchemy impl `OAuthStateRepositoryImpl`. Single-use consumption via `DELETE ... RETURNING verifier`.
- `redis_adapter.py` removed from the design. `redis[asyncio]` and `REDIS_URL` dropped from EP-00 deps and env list.
- Rate limiting uses `slowapi` with its in-memory backend for M1 (single BE replica). Scale-out will migrate to a shared store outside EP-00.
- New Celery periodic task `cleanup_expired_oauth_states` on a 10-minute schedule.

**Affected files**:
- `tasks/EP-00/design.md` — AD-01 rationale, AD-03 rewritten, sequence diagram, Security §2/§4/§5b, Alternatives, Layer Mapping.
- `tasks/EP-00/specs/auth/spec.md` — US-001 happy path, error cases, edge cases.
- `tasks/EP-00/tasks-backend.md` — Phases 0, 2, 3, 4, 5, 7, 8, 9 updated; adapter task replaced by repository task.
- `tasks/EP-00/tasks-frontend.md` — US-001 edge-case wording.
- `tasks/EP-00/tasks.md` — legacy pre-split file flagged superseded + realigned.

**No changes to**: AD-02 cookies, AD-04 user resolution, AD-05 first-login routing, AD-06 multi-workspace, AD-07 superadmin bootstrap. None depend on the state-storage medium.
