# EP-04 Frontend Tasks — Structured Specification & Quality Engine

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `LevelBadge` (low/medium/high/ready), `CompletenessBar`, `EmptyStateWithCTA` (no-spec placeholder), `HumanError`, semantic tokens, i18n `i18n/es/workitem.ts`. Section editor, dimension breakdown and next-step widget remain feature-specific. See `tasks/extensions.md#EP-19`.

Branch: `feature/ep-04-frontend`
Refs: EP-04
Depends on: EP-01 frontend (WorkItem types), EP-03 frontend (QuickActionMenu), EP-04 backend API, EP-19 catalog

---

## API Contract (Blocked by: EP-04 backend)

**Section shape:**
```typescript
interface Section {
  id: string
  section_type: SectionType
  content: string
  display_order: number
  is_required: boolean
  generation_source: 'llm' | 'manual' | 'revert'
  version: number
  updated_at: string
  updated_by: string
}

interface SpecificationResponse {
  work_item_id: string
  sections: Section[]
}
```

**Completeness response:**
```typescript
interface CompletenessResult {
  score: number           // 0–100
  level: 'low' | 'medium' | 'high' | 'ready'
  dimensions: DimensionResult[]
  computed_at: string
  cached: boolean
}

interface DimensionResult {
  name: string
  weight: number          // renormalized, sums to 1.0 across applicable dimensions
  filled: boolean
  score: number           // 0.0 or 1.0 (originally MVP-scoped — see decisions_pending.md)
  contribution: number    // weight * score
}
```

**Next-step response:**
```typescript
interface NextStepResult {
  next_step: string | null
  message: string | null
  blocking: boolean
  gaps_referenced: string[]
  suggested_validators: ValidatorSuggestion[]
}

interface ValidatorSuggestion {
  role: string
  reason: string
  configured: boolean
  setup_hint?: string
}
```

---

## Phase 1 — Type Definitions

- [ ] Implement `src/types/specification.ts`:
  - `SectionType` — union of all valid section type strings
  - `GenerationSource` type: `'llm' | 'manual' | 'revert'`
  - `Section` interface (full shape above)
  - `SpecificationResponse`, `SectionUpdateRequest`, `BulkSectionUpdateRequest`
  - `SectionVersion`: `{ id, section_id, version, content, generation_source, revert_from_version, created_at, created_by }`
- [ ] Implement `src/types/completeness.ts`: `CompletenessResult`, `DimensionResult`, `GapResult`, `NextStepResult`, `ValidatorSuggestion`

---

## Phase 2 — API Client Functions

Files: `src/lib/api/specification.ts`, `src/lib/api/completeness.ts`

- [ ] Implement `getSpecification(workItemId: string): Promise<SpecificationResponse>`
- [ ] Implement `generateSpecification(workItemId: string, force?: boolean): Promise<SpecificationResponse>`
- [ ] Implement `updateSection(workItemId: string, sectionId: string, content: string): Promise<Section>`
- [ ] Implement `bulkUpdateSections(workItemId: string, updates: { id: string, content: string }[]): Promise<Section[]>`
- [ ] Implement `getSectionVersions(workItemId: string, sectionId: string): Promise<SectionVersion[]>`
- [ ] Implement `revertSection(workItemId: string, sectionId: string, toVersion: number): Promise<Section>`
- [ ] Implement `getCompleteness(workItemId: string): Promise<CompletenessResult>`
- [ ] Implement `getGaps(workItemId: string): Promise<GapResult[]>`
- [ ] Implement `getNextStep(workItemId: string): Promise<NextStepResult>`
- [ ] [RED] Write unit tests using MSW: `generateSpecification` happy path, 409 concurrent generation throws `SpecGenerationInProgressError`, `updateSection` 422 on empty required section throws typed error

---

## Phase 3 — Data Fetching Hooks

Files: `src/hooks/use-specification.ts`, `src/hooks/use-completeness.ts`

- [ ] Implement `useSpecification(workItemId: string)`:
  - Returns `{ sections, isLoading, isError, refetch }`
  - Cache key: `['specification', workItemId]`
- [ ] Implement `useGenerateSpecification()` mutation:
  - On success: invalidates `['specification', workItemId]` and `['completeness', workItemId]` caches
  - Returns `{ generate, isGenerating, error }`
- [ ] Implement `useUpdateSection()` mutation: on success, invalidates spec + completeness cache
- [ ] Implement `useBulkUpdateSections()` mutation
- [ ] Implement `useCompleteness(workItemId: string)`:
  - Returns `{ completeness, isLoading }`
  - `staleTime: 60_000` (mirrors Redis TTL)
- [ ] Implement `useGaps(workItemId: string)`: returns gap list
- [ ] Implement `useNextStep(workItemId: string)`: returns next step result
- [ ] [RED] Write hook tests: `useCompleteness` loading state, data populated after fetch, cache invalidation triggered after `useUpdateSection` mutation success

---

## Phase 4 — SpecificationPanel Component

Component: `src/components/specification/specification-panel.tsx`

Props:
```typescript
interface SpecificationPanelProps {
  workItemId: string
  workItemType: WorkItemType
  canEdit: boolean  // is owner
}
```

- [ ] [RED] Write component tests:
  - Renders all sections for the work item in `display_order`
  - "Generate Specification" button visible when no sections exist
  - "Regenerate" button visible when sections already exist
  - Generation loading state: spinner + "Generating specification..." text
  - 409 concurrent error: "Generation already in progress" toast
  - Each section renders `SectionEditor`
  - Read-only when `canEdit = false`
- [ ] [GREEN] Implement `src/components/specification/specification-panel.tsx`:
  - Uses `useSpecification()` and `useGenerateSpecification()`
  - Loading skeleton: one placeholder per expected section (derived from `SECTION_CATALOG_FRONTEND` constant)
  - Empty state: "No specification yet. Click Generate to create one using AI."
  - Error state: error banner + retry

### Acceptance Criteria — SpecificationPanel

See also: specs/specification/spec.md (US-040, US-041)

WHEN `sections = []` (no specification yet)
THEN "No specification yet. Click Generate to create one using AI." is shown
AND "Generate Specification" button is visible

WHEN `sections` has existing entries
THEN "Regenerate" button is shown (not "Generate Specification")
AND each section is rendered as a `SectionEditor` in `display_order`

WHEN `canEdit = false`
THEN all `SectionEditor` instances are rendered in read-only mode
AND "Generate Specification"/"Regenerate" buttons are NOT shown

WHEN "Generate Specification" is clicked
THEN `useGenerateSpecification()` mutation fires
AND the button is replaced by a spinner with "Generating specification..." text
AND buttons are disabled during generation

WHEN generation returns HTTP 409 `SPEC_GENERATION_IN_PROGRESS`
THEN a toast notification: "Generation already in progress" is shown
AND no other UI state changes

WHEN `useSpecification()` is loading (initial fetch)
THEN N skeleton placeholder rows are shown (N = number of sections in `SECTION_CATALOG_FRONTEND` for the given type)

### SectionEditor Component (`src/components/specification/section-editor.tsx`)

Props:
```typescript
interface SectionEditorProps {
  section: Section
  canEdit: boolean
  onSave: (content: string) => Promise<void>
}
```

- [ ] [RED] Write component tests:
  - Renders section type as label with required indicator (`*`) for `is_required = true`
  - Renders content as plain text when not editing
  - Click on content (or "Edit" button) switches to edit mode
  - Edit mode: textarea with current content
  - Save button: calls `onSave(newContent)`, shows loading, returns to view mode on success
  - Cancel: reverts to original content
  - Empty content on required section: save button disabled + inline error "Required section cannot be empty"
  - `generation_source` badge: "AI Generated" chip when `llm`, "Manual" when `manual`, "Reverted" when `revert`
  - Version number shown (e.g., "v3")
  - "History" button → opens `SectionVersionHistory` panel
  - `QuickActionMenu` rendered alongside edit button (available actions depend on section type)
- [ ] [GREEN] Implement `src/components/specification/section-editor.tsx`

### Acceptance Criteria — SectionEditor

See also: specs/specification/spec.md (US-041)

WHEN `section.is_required = true`
THEN the label shows a `*` required indicator

WHEN the user is NOT in edit mode
THEN content is rendered as plain text (read-only)
AND edit affordance is only visible when `canEdit = true`

WHEN the user clears the content textarea and `section.is_required = true`
THEN the Save button is disabled
AND inline error reads "Required section cannot be empty"

WHEN the user clears the content textarea and `section.is_required = false`
THEN the Save button is enabled (empty optional section is valid)

WHEN Save is clicked and `onSave(newContent)` is pending
THEN the Save button shows a loading spinner and is disabled
AND Cancel is also disabled during save

WHEN `onSave()` resolves
THEN the editor returns to view mode with the new content displayed
AND the `generation_source` badge updates to "Manual"
AND version number increments (e.g., "v3" → "v4")

WHEN Cancel is clicked (no pending save)
THEN content reverts to `section.content` (pre-edit value)
AND edit mode is exited without calling `onSave()`

WHEN `section.generation_source = "llm"`
THEN badge reads "AI Generated"

WHEN `section.generation_source = "revert"`
THEN badge reads "Reverted"

### SectionVersionHistory Component (`src/components/specification/section-version-history.tsx`)

Props: `{ workItemId: string, sectionId: string, currentVersion: number, onRevert: (version: number) => void }`

- [ ] [GREEN] Implement: fetches `getSectionVersions()`, renders list of versions with content preview, "Revert to this version" button on each past version, loading state, empty state "No version history yet"
- [ ] [RED] Write component test: "Revert" button calls `onRevert(version.version)`, list rendered in descending version order

### Acceptance Criteria — SectionVersionHistory

See also: specs/specification/spec.md (SC-041-05, SC-041-06)

WHEN `getSectionVersions()` returns a list of versions
THEN versions are rendered in descending order (highest version number first)
AND each entry shows: version number, `created_at` date, `generation_source` badge, and a content preview

WHEN `getSectionVersions()` returns an empty list
THEN "No version history yet" is displayed

WHEN "Revert to this version" is clicked on version N
THEN `onRevert(N)` is called with the version number (not the content)
AND the button is disabled during the revert operation

WHEN the current version row is rendered (version == currentVersion)
THEN no "Revert" button is shown for it (cannot revert to current)

---

## Phase 5 — CompletenessPanel Component

Component: `src/components/quality/completeness-panel.tsx`

Props:
```typescript
interface CompletenessPanelProps {
  workItemId: string
}
```

- [ ] [RED] Write component tests:
  - Renders overall score as large number with level badge (low=red, medium=yellow, high=green, ready=teal)
  - Renders one row per dimension with weight, filled indicator, contribution
  - Blocking gaps shown with red indicator; warnings with yellow; info with gray
  - "Cached" badge shown when `cached = true`
  - Loading skeleton while fetching
- [ ] [GREEN] Implement `src/components/quality/completeness-panel.tsx`:
  - Uses `useCompleteness()` and `useGaps()`
  - Dimension rows: dimension name, weight percentage, filled/unfilled icon, `score * weight` contribution
  - Gap list below dimensions: grouped by severity
  - Polling: refetch completeness every 30s (stale after 30s since backend TTL is 60s)

### Acceptance Criteria — CompletenessPanel

See also: specs/quality-engine/spec.md (US-042)

WHEN `completeness.level = "low"` (score 0–39)
THEN the level badge is red

WHEN `completeness.level = "medium"` (score 40–69)
THEN the level badge is yellow/orange

WHEN `completeness.level = "high"` (score 70–89)
THEN the level badge is green

WHEN `completeness.level = "ready"` (score 90–100)
THEN the level badge is teal/blue

WHEN `completeness.cached = true`
THEN a "Cached" badge is shown alongside the score

WHEN `completeness.cached = false`
THEN no cached badge is shown

WHEN the gap list contains both blocking and warning gaps
THEN blocking gaps are rendered first (red)
AND warning gaps follow (yellow)

WHEN `useCompleteness()` is in loading state
THEN a skeleton placeholder is shown (not the score number)
AND no gap list is rendered

WHEN a section is saved (triggering `useUpdateSection()` mutation success)
THEN `useCompleteness()` cache is invalidated
AND the panel refetches and updates within one render cycle

---

## Phase 6 — NextStepWidget Component

Component: `src/components/quality/next-step-widget.tsx`

Props:
```typescript
interface NextStepWidgetProps {
  workItemId: string
  workItemType: WorkItemType
}
```

- [ ] [RED] Write component tests:
  - Renders `next_step` label and `message` text
  - Blocking next step shown with warning color and "Blocking" badge
  - `suggested_validators` rendered as a list: role, reason, configured/unconfigured status
  - Unconfigured role shows `setup_hint` and a link to workspace settings
  - `next_step = null` renders "Item is ready for export" message
  - Loading state
- [ ] [GREEN] Implement `src/components/quality/next-step-widget.tsx`:
  - Uses `useNextStep()`
  - Validator list: configured validators show green checkmark; unconfigured show amber "Not configured" badge
  - "Setup" link for unconfigured validators points to `/workspace/{slug}/settings/validators`

### Acceptance Criteria — NextStepWidget

See also: specs/quality-engine/spec.md (US-043)

WHEN `next_step = null` (exported item)
THEN the widget renders "This item has been exported to Jira." message
AND no action affordance is shown

WHEN `next_step = "assign_owner"` and `blocking = true`
THEN the widget shows a red/warning color scheme
AND a "Blocking" badge is visible

WHEN `next_step = "request_review"` and `blocking = false`
THEN the widget shows a neutral/green color scheme
AND no "Blocking" badge is shown

WHEN `suggested_validators` contains a validator with `configured = true`
THEN it shows a green checkmark next to the role name

WHEN `suggested_validators` contains a validator with `configured = false`
THEN it shows an amber "Not configured" badge
AND a "Setup" link is rendered pointing to `/workspace/{slug}/settings/validators`
AND `setup_hint` text is displayed (e.g., "Configure this role in workspace settings.")

WHEN `useNextStep()` is loading
THEN a skeleton placeholder is shown

---

## Phase 7 — Section Catalog Frontend Constant

File: `src/lib/section-catalog.ts`

- [ ] Implement `SECTION_CATALOG_FRONTEND: Record<WorkItemType, SectionConfig[]>` — mirrors backend Python `SECTION_CATALOG`; used for generating loading skeletons and section order before data loads
  - Each `SectionConfig`: `{ section_type: SectionType, display_order: number, required: boolean, display_label: string }`
- [ ] [RED] Write unit test: all 8 WorkItemType keys present, each has at least 1 required section, no duplicate `section_type` within a type

### Acceptance Criteria — Phase 7

See also: specs/specification/spec.md Section Type Reference table

WHEN `SECTION_CATALOG_FRONTEND["bug"]` is accessed
THEN it contains exactly: `summary (R)`, `steps_to_reproduce (R)`, `expected_behavior (R)`, `actual_behavior (R)`, `acceptance_criteria (R)`, `environment (O)`, `impact (O)`, `notes (O)` — matching the backend catalog
AND `summary` has `display_order = 1`

WHEN `SECTION_CATALOG_FRONTEND["spike"]` is accessed
THEN it contains `time_box (R)` and `output_definition (R)` as required sections

WHEN `tsc --noEmit` is run on `section-catalog.ts`
THEN no TypeScript errors — all `SectionType` values used are members of the `SectionType` union

---

## Phase 8 — Work Item Detail Page Integration

Update: `src/app/workspace/[slug]/work-items/[id]/page.tsx` (extends EP-03 additions)

- [ ] Add `SpecificationPanel` as the main content area (replaces plain description field from EP-01/EP-02)
- [ ] Add `CompletenessPanel` in the right sidebar
- [ ] Add `NextStepWidget` below completeness panel
- [ ] Layout: two-column layout on desktop (main content + sidebar), single column on mobile
- [ ] After `useUpdateSection()` mutation success: invalidate completeness + next-step caches so sidebar updates automatically

---

## Phase 9 — Responsive Behavior

- [ ] Specification panel: single-column stack on mobile (< 768px)
- [ ] `SectionEditor` textarea: minimum height 120px, auto-expand to content
- [ ] `CompletenessPanel`: dimension rows collapse to icon-only on mobile (< 768px) with tooltip on hover/tap
- [ ] `NextStepWidget`: full width on mobile
- [ ] All touch targets >= 44px (WCAG 2.5.5)

---

## Definition of Done

- [ ] All component tests pass
- [ ] `tsc --noEmit` clean
- [ ] No `any` types
- [ ] `SECTION_CATALOG_FRONTEND` matches backend catalog (all 8 types, correct required flags)
- [ ] Completeness panel updates after every section save (cache invalidation working)
- [ ] `SectionVersionHistory` shows all versions; revert creates new version with `generation_source='revert'`
- [ ] `NextStepWidget` shows `null` state correctly for exported items
- [ ] Responsive: detail page usable on 375px mobile viewport
