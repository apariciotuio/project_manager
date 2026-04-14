# EP-15 Frontend Tasks

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `TagChip`/`TagChipList` from the shared catalog (luminance-based contrast text is shared, do not reimplement). The tag admin panel keeps its feature-specific combobox and color picker; destructive actions (archive, merge) use `TypedConfirmDialog`. Use semantic tokens and i18n `i18n/es/tag.ts`. See `tasks/extensions.md#EP-19`.

TDD mandatory: RED → GREEN → REFACTOR. Write the failing test first.

---

## Group 1: TagChip Component

- [ ] **C-1** [RED] Write tests: `TagChip` renders label, applies color as inline style, shows icon when set, truncates long names with tooltip
- [ ] **C-1** [GREEN] Implement `TagChip` in `components/tags/TagChip.tsx`
  - Props: `tag: { id, name, color, icon, archived }`, `onRemove?: () => void`, `size?: 'sm' | 'md'`
  - Color applied as inline `style={{ backgroundColor: hexWithOpacity(color, 0.15), borderColor: color }}`
  - Text color: compute contrasting color (white/black) from background luminance
  - Archived state: strikethrough + reduced opacity + tooltip "This tag has been archived"
  - Max width 160px, truncate with `title` attribute for tooltip
- [ ] **C-2** [RED] Write tests: overflow badge renders `+N` when more than 4 chips in a list; clicking expands all
- [ ] **C-2** [GREEN] Implement `TagChipList` in `components/tags/TagChipList.tsx`
  - Props: `tags: Tag[]`, `maxVisible?: number` (default 4), `onRemove?: (tagId: string) => void`
  - Shows first `maxVisible` chips + overflow `+N` badge
  - Clicking overflow badge sets `expanded=true` in local state → all chips shown inline
- [ ] **C-3** [RED] Write test: `TagChip` with `onRemove` renders an `×` button; clicking triggers `onRemove` callback
- [ ] **C-3** [GREEN] Implement remove button variant
- [ ] **C-4** [REFACTOR] Extract `hexToContrastColor(hex: string): 'white' | 'black'` to `lib/color-utils.ts`; unit test it

---

## Group 2: TagInput Combobox

- [ ] **I-1** [RED] Write tests: `TagInput` calls autocomplete API after 2 characters with 200ms debounce; does not call on 1 character
- [ ] **I-1** [GREEN] Implement `TagInput` in `components/tags/TagInput.tsx` using `useCombobox` pattern (Headless UI or Radix)
  - Props: `workItemId: string`, `attachedTags: Tag[]`, `onTagAttached: (tag: Tag) => void`, `onTagDetached?: (tagId: string) => void`
  - Debounce: 200ms, minimum 2 chars to trigger search, empty focus shows recent 10
- [ ] **I-2** [RED] Write tests: suggestion list excludes archived tags; already-attached tags appear dimmed and are non-selectable
- [ ] **I-2** [GREEN] Implement suggestion filtering and dimming logic
- [ ] **I-3** [RED] Write tests: "Create tag" option appears when no match AND user has `tags:write` capability; absent otherwise
- [ ] **I-3** [GREEN] Implement on-the-fly create option; call `POST /api/v1/tags` then attach
- [ ] **I-4** [RED] Write test: on-the-fly create shows inline error on 409 conflict and surfaces conflicting tag in suggestions
- [ ] **I-4** [GREEN] Implement 409 error handling in create flow
- [ ] **I-5** [RED] Write test: selecting a suggestion calls `POST /api/v1/work-items/:id/tags` and invokes `onTagAttached`
- [ ] **I-5** [GREEN] Wire up attach call and callback
- [ ] **I-6** [REFACTOR] Extract `useTagAutocomplete(workItemId, query)` custom hook to `hooks/useTagAutocomplete.ts`

---

## Group 3: TagFilter (List Sidebar)

- [ ] **F-1** [RED] Write tests: `TagFilter` renders multi-select list of workspace active tags; selected tags update query params
- [ ] **F-1** [GREEN] Implement `TagFilter` in `components/tags/TagFilter.tsx`
  - Reads tags from `GET /api/v1/tags?archived=false`
  - Updates URL search params: `?tag_ids=a,b,c&tag_mode=and`
- [ ] **F-2** [RED] Write test: AND/OR toggle changes `tag_mode` param; default is `or`
- [ ] **F-2** [GREEN] Implement AND/OR toggle (segmented control / toggle button pair)
- [ ] **F-3** [RED] Write test: clearing all selected tags removes `tag_ids` and `tag_mode` from URL params
- [ ] **F-3** [GREEN] Implement clear behavior
- [ ] **F-4** [RED] Write test: `TagFilter` shows tag chips for selected tags; clicking a chip deselects it
- [ ] **F-4** [GREEN] Implement selected tag chip display in filter panel
- [ ] **F-5** Integration: wire `TagFilter` into existing list sidebar (EP-09 filter panel)
  - Add `TagFilter` below existing state/type filters
  - Ensure `tag_ids` + `tag_mode` params are passed to list API call alongside existing filter params

---

## Group 4: TagAdminPanel

- [ ] **P-1** [RED] Write tests: `TagAdminPanel` renders paginated tag table with name, color swatch, icon, archived status, action buttons
- [ ] **P-1** [GREEN] Implement `TagAdminPanel` in `components/tags/TagAdminPanel.tsx`
  - Fetches `GET /api/v1/tags` (all, including archived)
  - Columns: Color swatch | Name | Slug | Icon | Status | Actions
- [ ] **P-2** [RED] Write test: inline rename — double-click name enters edit mode; submit calls PATCH; cancel restores
- [ ] **P-2** [GREEN] Implement inline rename with optimistic update
- [ ] **P-3** [RED] Write test: color picker — clicking swatch opens hex input; valid hex updates preview; invalid shows error
- [ ] **P-3** [GREEN] Implement color picker (native `<input type="color">` + text input for hex value)
- [ ] **P-4** [RED] Write test: archive action shows confirmation modal; confirm calls PATCH `{ archived: true }`
- [ ] **P-4** [GREEN] Implement archive action with confirmation dialog
- [ ] **P-5** [RED] Write test: merge UI — select source tag, select target tag, confirm shows "X items will be re-tagged"; submit calls merge endpoint
- [ ] **P-5** [GREEN] Implement merge dialog with item count preview (fetched via a dry-run count or derived from tag usage)
- [ ] **P-6** [RED] Write test: create form — name input, color picker, icon selector; submit calls POST; 409 shows slug conflict error inline
- [ ] **P-6** [GREEN] Implement create form
- [ ] **P-7** [REFACTOR] Extract `useTagAdmin()` hook that encapsulates all mutation state and API calls

---

## Group 5: Integration — Work Item Header

- [ ] **W-1** Add `TagChipList` to work item header/detail view
  - Source: `work_item.tag_ids` resolved to full tag objects from workspace tag cache
  - Show `TagInput` combobox when user clicks "+ Add tag" or clicks into the chip area (edit mode)
- [ ] **W-2** [RED] Write integration test: adding a tag from work item detail updates the chip list without page reload
- [ ] **W-2** [GREEN] Wire `onTagAttached` callback to update local state (optimistic) and invalidate React Query cache
- [ ] **W-3** [RED] Write integration test: removing a tag chip calls DELETE and updates chip list optimistically
- [ ] **W-3** [GREEN] Wire `onRemove` on chips to call detach endpoint

---

## Group 6: Integration — List Sidebar (EP-09 Extension)

- [ ] **L-1** Verify EP-09 list API service passes `tag_ids` and `tag_mode` params when present in URL
- [ ] **L-2** [RED] Write integration test: selecting tags in `TagFilter` updates the list results
- [ ] **L-2** [GREEN] Wire filter state to list query; ensure React Query key includes `tag_ids` and `tag_mode`
- [ ] **L-3** Test: kanban board view — tag filter applies per-column, column counts update, empty columns stay visible

---

## Acceptance Criteria

- `TagChip` renders correctly for active, archived, and overflow states; WCAG AA contrast enforced
- `TagInput` debounces at 200ms, excludes archived tags, creates on-the-fly with capability guard
- `TagFilter` AND/OR toggle updates URL params; clears cleanly
- `TagAdminPanel` covers create, rename, recolor, archive, merge — all with confirmation where destructive
- All API calls use workspace-scoped endpoints; no workspace ID passed from client
- All mutations use optimistic updates with React Query `invalidateQueries` on error rollback
- All components fully typed (TypeScript strict); no `any`
