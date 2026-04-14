# EP-02 Frontend Tasks — Capture Form, Draft Auto-Save & Templates

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `TypeBadge` shared icon map (remove local `TypeSelector` icon duplication), `HumanError` for save errors, semantic tokens, i18n `i18n/es/workitem.ts` + `i18n/es/common.ts`. `DraftResumeBanner` and auto-save debounce UX remain feature-specific. See `tasks/extensions.md#EP-19`.

Branch: `feature/ep-02-frontend`
Refs: EP-02
Depends on: EP-00 frontend, EP-01 frontend (WorkItem types), EP-02 backend API, EP-19 catalog

---

## API Contract (Blocked by: EP-02 backend)

| Endpoint | Trigger | Frontend action |
|----------|---------|-----------------|
| `GET /api/v1/work-item-drafts` | App mount / page open | Resume draft if present |
| `POST /api/v1/work-item-drafts` | 3s after typing stops | Auto-save; handle 409 conflict |
| `DELETE /api/v1/work-item-drafts/{id}` | User clicks "Discard" | Remove draft, clear form |
| `PATCH /api/v1/work-items/{id}/draft` | 3s after typing in committed Draft item | Auto-save committed item |
| `GET /api/v1/templates?type={type}` | Type selector change | Populate description editor |
| `POST /api/v1/templates` | Admin template management | Admin panel only |

**POST /work-item-drafts response:**
```typescript
{ data: { draft_id: string, local_version: number } }
```
**409 conflict response:**
```typescript
{ error: { code: "DRAFT_VERSION_CONFLICT", details: { server_version: number, server_data: DraftData } } }
```
**Template shape:**
```typescript
{ id: string, type: WorkItemType, name: string, content: string, is_system: boolean }
```

---

## Phase 1 — Type Definitions

- [ ] Implement `src/types/draft.ts`:
  - `DraftData` interface: `{ title?: string, type?: WorkItemType, description?: string, priority?: string, [key: string]: unknown }`
  - `WorkItemDraft` interface: `{ id: string, workspace_id: string, data: DraftData, local_version: number, incomplete: boolean, updated_at: string, expires_at: string }`
  - `DraftConflict` type: `{ server_version: number, server_data: DraftData }`
- [ ] Implement `src/types/template.ts`: `Template` interface with all fields

---

## Phase 2 — API Client Functions

File: `src/lib/api/drafts.ts` and `src/lib/api/templates.ts`

- [ ] Implement `upsertPreCreationDraft(workspaceId, data, localVersion): Promise<{ draft_id: string, local_version: number }>` — throws typed `DraftConflictError` on 409
- [ ] Implement `getPreCreationDraft(workspaceId): Promise<WorkItemDraft | null>`
- [ ] Implement `discardPreCreationDraft(draftId): Promise<void>`
- [ ] Implement `saveCommittedDraft(workItemId, draftData): Promise<{ id: string, draft_saved_at: string }>`
- [ ] Implement `getTemplate(type: WorkItemType, workspaceId: string): Promise<Template | null>`
- [ ] Implement `createTemplate(data): Promise<Template>`
- [ ] Implement `updateTemplate(id, data): Promise<Template>`
- [ ] Implement `deleteTemplate(id): Promise<void>`
- [ ] [RED] Write unit tests for each function using MSW: `upsertPreCreationDraft` happy path, 409 throws `DraftConflictError` with server data attached

---

## Phase 3 — useAutoSave Hook

File: `src/hooks/useAutoSave.ts`

Hook contract:
```typescript
function useAutoSave(params: {
  workspaceId: string
  draftId: string | null
  onDraftSaved: (draftId: string, version: number) => void
  onConflict: (serverData: DraftData, serverVersion: number) => void
}): {
  save: (data: DraftData) => void   // debounced 3s
  isSaving: boolean
  lastSavedAt: Date | null
}
```

- [ ] [RED] Write tests for `useAutoSave`:
  - `save()` called repeatedly within 3s window fires only once
  - `save()` followed by 3s idle fires the API call with latest data
  - Successful save calls `onDraftSaved` with returned `draft_id` and `local_version`
  - 409 API response calls `onConflict` with `server_data` and `server_version`
  - Unmount clears pending debounce timer (no state update after unmount)
  - `isSaving` is true during API call, false after completion
  - `lastSavedAt` is set on successful save
- [ ] [GREEN] Implement `src/hooks/useAutoSave.ts`:
  - Debounce via `useRef` + `setTimeout` (not lodash — keep it explicit)
  - Track `localVersion` in `useRef` (not state — no re-render on version bump)
  - Clear timer in `useEffect` cleanup
- [ ] [REFACTOR] Verify hook has no side effects after unmount; timer cleared on cleanup

### Acceptance Criteria — useAutoSave

See also: specs/capture/spec.md (US-021)

WHEN `save(data)` is called 5 times within a 3-second window
THEN `upsertPreCreationDraft()` is called exactly once (with the latest data)

WHEN `save(data)` is called and 3 seconds elapse with no further calls
THEN `upsertPreCreationDraft()` is called exactly once
AND `isSaving` transitions to `true` during the call and back to `false` after

WHEN `upsertPreCreationDraft()` resolves successfully
THEN `onDraftSaved(draft_id, local_version)` is called
AND `lastSavedAt` is updated to the current time

WHEN `upsertPreCreationDraft()` returns a 409 conflict
THEN `onConflict(server_data, server_version)` is called
AND `isSaving` is set to `false`
AND `lastSavedAt` is NOT updated

WHEN the component unmounts while a debounce timer is pending
THEN the timer is cleared and `upsertPreCreationDraft()` is NOT called
AND no React state-update-after-unmount warning is triggered

---

## Phase 4 — CaptureForm Component

Component: `src/components/capture-form/capture-form.tsx`

- [ ] [RED] Write component tests for `CaptureForm`:
  - Renders with empty form when no existing draft
  - `DraftResumeBanner` shown when draft exists on mount (mocked `getPreCreationDraft` returns draft)
  - `SubmitButton` disabled when title < 3 chars
  - `SubmitButton` disabled when no type selected
  - `SubmitButton` enabled when title ≥ 3 chars AND type selected
  - Type change triggers template fetch (mock `getTemplate` call captured)
  - Confirmation modal shown when type changes and description is non-empty
  - Template populates description editor on confirm; description reverts on cancel
- [ ] [RED] Write tests for `StalenessWarning`: renders when `onConflict` is called by `useAutoSave`, "Keep mine" keeps current form data, "Load latest" replaces form data with `server_data`

### Acceptance Criteria — CaptureForm

See also: specs/capture/spec.md (US-020, US-021), specs/templates/spec.md (US-022)

WHEN the page mounts and `getPreCreationDraft()` returns a draft
THEN `DraftResumeBanner` is visible with "Resume" and "Discard" options
AND the form fields are empty (draft is NOT auto-applied until user clicks Resume)

WHEN the user clicks "Resume" in `DraftResumeBanner`
THEN form fields are populated with `draft.data`
AND the banner is hidden

WHEN the user clicks "Discard" in `DraftResumeBanner`
THEN `discardPreCreationDraft(draft.id)` is called
AND form fields remain empty
AND the banner is hidden

WHEN title is 2 chars (user typed "ab")
THEN SubmitButton is disabled

WHEN title is 3+ chars AND type is selected
THEN SubmitButton is enabled

WHEN the type selector changes from "bug" to "task" and description is already non-empty
THEN a confirmation modal is shown: "Changing type will replace the current template. Continue?"

WHEN user confirms the type change
THEN `getTemplate("task", workspaceId)` is called
AND description editor is replaced with the new template content (or cleared if none)

WHEN user cancels the type change
THEN type selector reverts to "bug"
AND description is unchanged

WHEN `useAutoSave.onConflict` fires with `server_data` and `server_version`
THEN `StalenessWarning` is rendered inline (not a blocking modal)
AND "Keep mine" dismisses the warning without changing form data
AND "Load latest" replaces form data with `server_data` and hides the warning
- [ ] [GREEN] Implement `src/components/capture-form/capture-form.tsx` with sub-components:
  - `TypeSelector` — dropdown of 8 types with display labels and icons; triggers template fetch on change with 200ms delay (avoids fetch on rapid cycling)
  - `TitleInput` — controlled, fires debounced auto-save on change
  - `DescriptionEditor` — textarea (Markdown, EP-03 may upgrade to rich editor); pre-populated from template
  - `SubmitButton` — disabled rule: `title.length < 3 || !type`
  - `CancelButton` — cancel/close logic:
    - If form has unsaved content AND no auto-save has succeeded yet (`lastSavedAt === null`): show confirmation dialog "Discard unsaved changes?" before closing
    - If auto-save succeeded at least once (`lastSavedAt !== null`): close without confirmation (draft persists on server; user can resume later)
    - If form is empty: close without confirmation
    - Acceptance criteria:
      - WHEN user clicks cancel with unsaved content and no prior auto-save THEN confirmation dialog appears
      - WHEN user confirms discard THEN `discardPreCreationDraft()` is called and user navigates back
      - WHEN user clicks cancel and auto-save has already succeeded THEN closes immediately with no dialog (draft remains)
    - [RED] Test: cancel with dirty form + no prior save → dialog appears; cancel with prior save → no dialog; confirm discard → navigates back
- [ ] [GREEN] Implement `src/components/capture-form/draft-resume-banner.tsx`:
  - Props: `{ draft: WorkItemDraft, onResume: () => void, onDiscard: () => void }`
  - Shows when draft found on mount
  - "Resume" → populates form with `draft.data`
  - "Discard" → calls `discardPreCreationDraft(draft.id)`, hides banner
- [ ] [GREEN] Implement `src/components/capture-form/staleness-warning.tsx`:
  - Props: `{ serverData: DraftData, serverVersion: number, onKeepMine: () => void, onLoadLatest: (data: DraftData) => void }`
  - Non-blocking inline banner (not modal)
- [ ] Wire `useAutoSave` into `CaptureForm`: call `save(formData)` on any field change
- [ ] Wire template fetch using React Query with `staleTime: 5 * 60 * 1000` on type selector change

---

## Phase 5 — WorkItemHeader Extensions

Component: `src/components/work-items/work-item-header.tsx`

- [ ] [RED] Write component tests for `WorkItemHeader`:
  - Renders `TypeBadge` with correct color per type
  - Renders `StateChip` with correct color coding
  - Renders owner avatar; shows initial fallback when `avatar_url` is null
  - Renders `CompletenessBar` filled to `completeness_score` percent
  - `NextStepHint` shown when `completeness_score < 30`
  - `NextStepHint` hidden when `completeness_score >= 30`
  - `SuspendedBadge` shown when `owner_suspended_flag = true`

Props:
```typescript
interface WorkItemHeaderProps {
  workItem: WorkItemResponse
  canEdit: boolean  // derived from auth: is owner
}
```

- [ ] [GREEN] Implement `src/components/work-items/work-item-header.tsx`:
  - `TypeBadge` — colored chip per type (8 colors defined in Tailwind config)
  - `StateChip` — primary state displayed; color: draft=gray, in_clarification=blue, in_review=indigo, changes_requested=orange, partially_validated=yellow, ready=green, exported=teal
  - `OwnerWidget` — avatar (16x16 circle) + full name; amber "SUSPENDED" badge when `owner_suspended_flag = true`
  - `CompletenessBar` — Tailwind `w-full` progress bar, fill color: <30=red, 30-69=yellow, ≥70=green
  - `NextStepHint` — small text below bar: "Add more details to enable review" (shown only when score < 30)
- [ ] [GREEN] Implement owner initials fallback: takes first char of first name + first char of last name from `full_name`
- [ ] Verify header renders correctly from `POST /work-items` 201 response (no second fetch required)

---

## Phase 6 — Create Work Item Page (EP-02 Extended)

Update: `src/app/workspace/[slug]/work-items/new/page.tsx` (extends EP-01 skeleton)

- [ ] Replace EP-01 plain form with `CaptureForm` component
- [ ] On page mount: call `getPreCreationDraft(workspaceId)`, pass to `CaptureForm` for resume
- [ ] On successful `POST /work-items` (201): call `discardPreCreationDraft()` to clean up draft, redirect to `/workspace/{slug}/work-items/{id}`
- [ ] Pass `template_id` from form state to `createWorkItem()` request body when template was applied

---

## Definition of Done

- [ ] All component tests pass
- [ ] `tsc --noEmit` clean
- [ ] No `any` types
- [ ] `useAutoSave` debounces correctly: only one API call per 3s idle window verified in test
- [ ] Draft resume banner appears on page revisit when draft exists
- [ ] Staleness warning appears and both resolution paths work
- [ ] Template populates description when type is selected; confirmation modal shown before overwrite
- [ ] `WorkItemHeader` completeness bar reflects `completeness_score` accurately
- [ ] `NextStepHint` visible only when score < 30
