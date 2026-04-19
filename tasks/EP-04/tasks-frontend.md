# EP-04 Frontend Tasks — Structured Specification & Quality Engine

> **Follows EP-19 (Design System & Frontend Foundations)**. Adopt `LevelBadge` (low/medium/high/ready), `CompletenessBar`, `EmptyStateWithCTA` (no-spec placeholder), `HumanError`, semantic tokens, i18n `i18n/es/workitem.ts`. Section editor, dimension breakdown and next-step widget remain feature-specific. See `tasks/extensions.md#EP-19`.

Branch: `main` (implemented directly on main, committed)
Refs: EP-04
Depends on: EP-01 frontend (WorkItem types), EP-03 frontend (QuickActionMenu), EP-04 backend API, EP-19 catalog

---

## API Contract (Live — EP-04 backend shipped)

**Actual backend response shapes (from shipped controllers):**

```typescript
// GET /specification → { data: { work_item_id, sections: Section[] } }
interface Section {
  id: string
  work_item_id: string
  section_type: string
  content: string
  display_order: number
  is_required: boolean
  generation_source: 'llm' | 'manual' | 'revert'
  version: number
  created_at: string
  updated_at: string
  created_by: string
  updated_by: string
}

// GET /completeness → { data: CompletenessReport }
// Note: dimension.score is 0.0-1.0 float; overall score is 0-100 int
// Note: dimensions field uses 'dimension' key (not 'name')
// Note: no 'computed_at' in actual response (not in controller)

// GET /gaps → { data: GapItem[] } — array directly (no findings wrapper, no score)
// Note: differs from EP-03 GapReport shape; getGapReport maps to GapReport for compat

// GET /next-step → { data: NextStepResult }
```

---

## Phase 1 — Type Definitions ✅

- [x] `frontend/lib/types/specification.ts` — `SectionType`, `GenerationSource`, `Section`, `SpecificationApiResponse`, `SectionUpdateRequest`, `SectionVersion`, `CompletenessDimension`, `CompletenessReport`, `CompletenessApiResponse`, `GapItem`, `GapsApiResponse`, `ValidatorSuggestion`, `NextStepResult`, `NextStepApiResponse` (commit 817a1c1)
- [x] `frontend/lib/types/work-item-detail.ts` — deprecated overlapping types with `@deprecated` JSDoc; reconciled `CompletenessDimension.score` as 0.0–1.0 float, added `cached` field to `CompletenessData` (commit 817a1c1)

---

## Phase 2 — API Client + Hooks ✅

- [x] `frontend/lib/api/gaps.ts` — removed EP-04-not-shipped stub from `getGapReport`; now hits real `GET /gaps` endpoint; maps `GapItem[]` → `GapReport` for EP-03 backward compat (commit 817a1c1)
- [x] `frontend/hooks/work-item/use-sections.ts` — `useSections(workItemId, options)` with optimistic patch + rollback on error, `onPatchSuccess` callback (commit 817a1c1)
- [x] `frontend/hooks/work-item/use-next-step.ts` — `useNextStep(workItemId)` (commit 817a1c1)
- [x] `frontend/hooks/work-item/use-completeness.ts` — existing hook kept, already hits real endpoint (commit 817a1c1)
- [x] `frontend/hooks/work-item/use-gaps.ts` — existing hook kept; stub removal in `getGapReport` propagates (commit 817a1c1)
- [x] Tests: `use-sections` (5 tests), `use-next-step` (4 tests), `use-gaps-ep04` (3 tests) — all pass (commit 817a1c1)
- [x] Updated `__tests__/lib/api/gaps.test.ts` and `gap-panel.test.tsx`, `clarification-tab.test.tsx` to EP-04 array format (commit 817a1c1)

**Deferred (no BE endpoint for these in EP-04):**
- [ ] `generateSpecification` / POST `/specification/generate` — backend defers to Dundun; no EP-04 endpoint shipped
- [ ] `bulkUpdateSections` — backend defers bulk PATCH
- [ ] `getSectionVersions` / `revertSection` — backend endpoint path `/sections/{id}/versions` not in shipped controllers

---

## Phase 3 — SpecificationSectionsEditor ✅

- [x] `frontend/components/work-item/specification-sections-editor.tsx` — debounced auto-save (600ms), generation badge per section, version chip, disabled when `canEdit=false`, saving indicator, skeleton loading (commit 489cb57)
- [x] Component tests: 6 tests (skeleton, renders sections, read-only, saving state, badge, label) (commit 489cb57)
- [x] i18n under `workspace.itemDetail.specification.*` in `en.json` and `es.json` (commit 489cb57)

**Not implemented (no design precedent):**
- `applicable` toggle (Switch) per section — EP-04 backend `PATCH /sections/{id}` only accepts `content` field; no `applicable` field in `UpdateSectionRequest`
- Per-section completeness badge — completeness report has no section-level mapping
- Field-level error via `useFormErrors` — `ApiError.field` pattern not applicable here (section errors are domain errors, not field validation errors)

---

## Phase 4 — CompletenessPanel ✅

- [x] `frontend/components/work-item/completeness-panel.tsx` — score ring, LevelBadge, per-dimension bars with CompletenessBar, gap overlay on matching dimension rows, cached badge (commit 489cb57)
- [x] Component tests: 7 tests (skeleton, score, level badge, dimension rows, gap overlay, cached) (commit 489cb57)

---

## Phase 5 — NextStepHint ✅

- [x] `frontend/components/work-item/next-step-hint.tsx` — hint message, blocking badge, suggested validators with configured/not-configured status, terminal state for `null` next_step (commit 489cb57)
- [x] Component tests: 7 tests (commit 489cb57)

**CTA actions:**
- `open_clarification`, `open_breakdown`, `request_review`, `mark_ready` — CTA wire requires callback props from parent page (slug). Since EP-04 `/next-step` returns rule IDs not CTA objects, and the backend `NextStepResult` has no `cta` field in the shipped controller, CTA wiring is deferred. The prompt's CTA shape `{ label, action, params }` is not in the live contract.

---

## Phase 6 — Detail Page Integration ✅

- [x] `frontend/app/workspace/[slug]/items/[id]/page.tsx` — replaces `SpecificationTab` with 2-column grid: `SpecificationSectionsEditor` (2/3) + `CompletenessPanel` + `NextStepHint` (1/3) (commit af0f867)
- [x] `frontend/components/work-item/specification-tab.tsx` — `@deprecated` JSDoc added, kept importable (commit af0f867)
- [x] `work-item-detail.test.tsx` — updated SPEC fixture to EP-04 shape, added `/next-step` handler (commit af0f867)

---

## Definition of Done — Status

| Criterion | Status |
|-----------|--------|
| All component tests pass | ✅ 94 files, 659 tests |
| `tsc --noEmit` clean | ✅ |
| No `any` types | ✅ |
| Completeness panel updates after section save | ✅ via `onPatchSuccess` → `refetch` |
| `NextStepHint` shows null state for terminal items | ✅ |
| Responsive 2-col layout on md+ | ✅ (`md:grid-cols-3`) |

**Status: COMPLETED** (2026-04-17)
