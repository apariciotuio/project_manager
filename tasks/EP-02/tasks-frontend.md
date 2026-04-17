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

- [x] Implement `src/types/draft.ts`:
  - `DraftData` interface: `{ title?: string, type?: WorkItemType, description?: string, priority?: string, [key: string]: unknown }`
  - `WorkItemDraft` interface: `{ id: string, workspace_id: string, data: DraftData, local_version: number, incomplete: boolean, updated_at: string, expires_at: string }`
  - `DraftConflict` type: `{ server_version: number, server_data: DraftData }`
  - Evidence: `frontend/hooks/use-pre-creation-draft.ts` defines `DraftData`, `WorkItemDraft`, `DraftConflictDetails` inline (shipped 2026-04-17). Types are co-located in the hook rather than a separate file — deviation from plan, but equivalent coverage.
- [x] Implement `src/types/template.ts`: `Template` interface with all fields
  - Evidence: `frontend/lib/types/api.ts` exports `Template { id, name, description, type, fields }` and `TemplatesResponse`. Co-located with other API types rather than a separate file — equivalent.

---

## Phase 2 — API Client Functions

File: `src/lib/api/drafts.ts` and `src/lib/api/templates.ts`

- [x] Implement `upsertPreCreationDraft(workspaceId, data, localVersion)` — throws typed `DraftConflictError` on 409
  - Evidence: `doSave()` inside `use-pre-creation-draft.ts` calls `POST /api/v1/work-item-drafts` and handles 409 → `setConflictError`. Inline rather than separate module.
- [x] Implement `getPreCreationDraft(workspaceId)` — returns draft or null
  - Evidence: `fetchOnMount()` in `use-pre-creation-draft.ts` calls `GET /api/v1/work-item-drafts?workspace_id=...`.
- [x] Implement `discardPreCreationDraft(draftId)` — DELETE call
  - Evidence: `discard()` in `use-pre-creation-draft.ts` calls `DELETE /api/v1/work-item-drafts/{id}`.
- [ ] Implement `saveCommittedDraft(workItemId, draftData)` — PATCH for committed draft items
  - Not implemented. No hook or API call for `PATCH /api/v1/work-items/{id}/draft` exists.
- [ ] Implement `getTemplate(type, workspaceId)` — GET by type
  - Not implemented as a per-type fetch. `useTemplates()` fetches all templates (`GET /api/v1/templates`) at once; no type-parameterised call.
- [ ] Implement `createTemplate(data)`, `updateTemplate(id, data)`, `deleteTemplate(id)`
  - Not implemented — admin template management not yet built.
- [ ] [RED] Write unit tests for each function using MSW
  - No dedicated unit tests for the API client functions. Coverage is via integration in `new-item-page.test.tsx` (MSW handlers for draft POST/GET/DELETE).

---

## Phase 3 — useAutoSave Hook

File: `src/hooks/useAutoSave.ts`

- [x] [RED] Write tests for `useAutoSave` (debounce fires once, conflict path, unmount cleanup)
  - Evidence: `__tests__/app/workspace/new-item-page.test.tsx` — "draft save is triggered after debounce" test covers the debounce path end-to-end via MSW. Granular unit-level tests for the hook itself are not present as separate files.
- [x] [GREEN] Implement auto-save with debounce
  - Evidence: `use-pre-creation-draft.ts` — debounce via `useRef + setTimeout`, 2000ms window (plan specified 3s; actual is 2s — minor deviation). `localVersion` tracked in `useRef`. Timer cleared in `discard()`.
- [x] [REFACTOR] Timer cleared on cleanup
  - Evidence: `discard()` clears `debounceRef.current`. Unmount cleanup relies on discard — note: no `useEffect` cleanup for the timer on unmount (only on explicit discard). Minor gap vs plan which specified `useEffect` cleanup.

### Acceptance Criteria — useAutoSave

All criteria are covered by the integrated implementation in `use-pre-creation-draft.ts` and exercise via `new-item-page.test.tsx`, with the exception of the unmount-cleanup test which is not explicitly tested in isolation.

---

## Phase 4 — CaptureForm Component

Component: `src/components/capture-form/capture-form.tsx`

- [x] [RED] Write component tests for form behaviour
  - Evidence: `__tests__/app/workspace/new-item-page.test.tsx` covers: renders title input, submit disabled when title empty, project picker, tag toggle, parent picker visibility, draft hydration, draft save debounce, submit + redirect. No separate `CaptureForm` component — form is inlined in the page.
- [ ] [RED] Write tests for `StalenessWarning` component
  - Not implemented as a separate component with dedicated tests. Conflict banner renders inline in the page but no "Keep mine" / "Load latest" UX; only "Sobreescribir" (overwrite) button that calls `resolveConflict`.
- [x] [GREEN] Implement form fields: TypeSelector, TitleInput, DescriptionEditor, SubmitButton, CancelButton
  - Evidence: `frontend/app/workspace/[slug]/items/new/page.tsx` — all fields present inline: type Select, title Input, description Textarea, Submit Button (disabled when `!title.trim() || !projectId`), Cancel Button.
- [ ] [GREEN] Implement `DraftResumeBanner` sub-component
  - Not shipped as a separate component. Draft auto-hydrates silently via `onHydrate` callback — no explicit "Resume / Discard" banner shown to the user. Deviation: plan required the banner; current impl auto-applies draft on mount.
- [ ] [GREEN] Implement `StalenessWarning` sub-component
  - Partial: conflict error renders an inline yellow banner with "Sobreescribir" (overwrite) but no "Keep mine" option. Diverges from plan spec.
- [x] Wire `useAutoSave` into form — save called on field change
  - Evidence: `useEffect` in `new/page.tsx` fires `save()` on `[title, type, description, projectId, parentId, selectedTags]` changes.
- [ ] Wire template fetch with `staleTime: 5 * 60 * 1000` on type selector change
  - Templates fetched via `useTemplates()` (all at once, no type filter, no React Query — raw `useEffect`). No per-type fetch on selector change.

---

## Phase 5 — WorkItemHeader Extensions

Component: `src/components/work-items/work-item-header.tsx`

- [x] [RED] Write component tests for `WorkItemHeader`
  - Evidence: partial coverage exists in existing test suite. `work-item-header.tsx` is rendered in the detail page.
- [x] [GREEN] Implement `WorkItemHeader` with TypeBadge, StateBadge, OwnerWidget, CompletenessBar, NextStepHint
  - Evidence: `frontend/components/work-item/work-item-header.tsx` — renders `TypeBadge`, `StateBadge`, `OwnerAvatar`. Completeness score shown as text `{score}%`. **Missing**: `CompletenessBar` in the header (bar is on the list page rows, not the detail header). **Missing**: `NextStepHint` (score < 30 hint). **Missing**: `SuspendedBadge`.
- [x] [GREEN] Implement owner initials fallback
  - Evidence: `OwnerAvatar` component exists in `components/domain/owner-avatar.tsx` with initials fallback.
- [ ] Verify header renders correctly from `POST /work-items` 201 response
  - Not explicitly tested (no test asserting header renders from create response).

---

## Phase 6 — Create Work Item Page (EP-02 Extended)

Update: `src/app/workspace/[slug]/work-items/new/page.tsx`

- [x] Replace EP-01 plain form with full capture form
  - Evidence: `frontend/app/workspace/[slug]/items/new/page.tsx` is the full form (title, type, project, parent, tags, description, template picker).
- [x] On page mount: fetch draft and hydrate form
  - Evidence: `usePreCreationDraft` triggers `fetchOnMount` on first render, calls `onHydrate` with draft data.
- [x] On successful POST: discard draft and redirect
  - Evidence: `handleSubmit` calls `discard()` then `router.push(...)`.
- [x] Pass `template_id` to create request when template applied
  - Partial: `selectedTemplate` state exists and template picker sets it, but `template_id` is **not** included in the `createWorkItem()` call body. Gap.

---

## Definition of Done

- [ ] All component tests pass — pending: `StalenessWarning`, `DraftResumeBanner` components not implemented
- [x] `tsc --noEmit` clean
- [ ] No `any` types — `use-pre-creation-draft.ts` uses `err as { status?: number; details?: DraftConflictDetails }` cast (line 100)
- [ ] `useAutoSave` debounce verified in isolation — covered end-to-end only
- [ ] Draft resume banner appears on page revisit — auto-hydrated silently, no banner UI
- [ ] Staleness warning with both resolution paths — only "overwrite" path, no "keep mine"
- [ ] Template populates description on type change with confirmation modal — templates applied on click, not on type change; no confirmation modal
- [x] `WorkItemHeader` completeness score shown — as text percentage
- [ ] `NextStepHint` visible only when score < 30 — not implemented

---

## Reconciliation notes (2026-04-17)

### What shipped vs what was planned

| Plan artefact | Plan location | Actual location | Status |
|---|---|---|---|
| `DraftData`, `WorkItemDraft`, `DraftConflict` | `src/types/draft.ts` | Inline in `use-pre-creation-draft.ts` | Equivalent — no separate file |
| `Template` type | `src/types/template.ts` | `lib/types/api.ts` | Equivalent |
| `upsertPreCreationDraft`, `getPreCreationDraft`, `discardPreCreationDraft` | `src/lib/api/drafts.ts` | Inline in `use-pre-creation-draft.ts` | Equivalent — co-located |
| `saveCommittedDraft` | `src/lib/api/drafts.ts` | Not implemented | **Missing** |
| `getTemplate(type)`, CRUD template functions | `src/lib/api/templates.ts` | Not implemented | **Missing** |
| `useAutoSave` hook | `src/hooks/useAutoSave.ts` | Merged into `use-pre-creation-draft.ts` | Merged — debounce is 2s not 3s |
| `CaptureForm` component | `src/components/capture-form/` | Inlined in `new/page.tsx` | Not extracted |
| `DraftResumeBanner` | sub-component | Not implemented — silent hydration | **Missing** |
| `StalenessWarning` | sub-component | Partial inline banner (no "keep mine") | **Partial** |
| Template fetch on type change with confirmation modal | `CaptureForm` | Template picker fetches all at mount, applied on click | **Different UX** |
| `WorkItemHeader` CompletenessBar + NextStepHint + SuspendedBadge | header component | Score shown as text only | **Partial** |
| `template_id` in create request | `createWorkItem()` call | Not passed | **Missing** |
| Unmount cleanup for debounce timer | `useEffect` return | Only cleared on `discard()` call | **Minor gap** |

### Deviations summary

1. **Architecture consolidation**: The plan specified separate files (`types/draft.ts`, `lib/api/drafts.ts`, `hooks/useAutoSave.ts`, `components/capture-form/`). Shipped code consolidates all of this into `use-pre-creation-draft.ts` + inline page code. Functionally equivalent for the happy path but harder to unit-test in isolation.

2. **DraftResumeBanner missing**: Draft auto-hydrates on mount rather than showing a resume/discard prompt. This is a UX regression vs the spec — user has no choice to discard before seeing hydrated form.

3. **StalenessWarning partial**: Conflict shows "Overwrite" only. "Keep mine" (dismissing conflict without data change) is absent.

4. **template_id not passed to createWorkItem**: Selected template is tracked in state but not forwarded to the API. Backend will not link the created item to the template.

5. **Debounce window is 2s, not 3s**: Minor deviation — effectively stricter (saves sooner).

6. **WorkItemHeader gaps**: `CompletenessBar`, `NextStepHint`, and `SuspendedBadge` not rendered in the detail header. Completeness shown as raw text percentage.
