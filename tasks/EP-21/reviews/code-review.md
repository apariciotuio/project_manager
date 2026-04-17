# EP-21 Code Review

**Range:** `6d242ec..HEAD` (14 commits, 56 files, +4880/-317)
**Reviewer:** code-reviewer agent
**Date:** 2025-04-17

---

## Must Fix

### MF-1 -- Missing auth on 4 tag endpoints (IDOR / unauthenticated access)

**File:** `backend/app/presentation/controllers/tag_controller.py:128-171, 215-236`

`rename_tag` (PATCH), `archive_tag` (DELETE), `remove_tag_from_work_item` (DELETE), and `list_work_item_tags` (GET) have **no `Depends(get_current_user)`**. Any unauthenticated caller can rename/archive any tag or detach tags from work items by guessing UUIDs. The other 3 endpoints in the same file (`create_tag`, `list_tags`, `add_tag_to_work_item`) correctly require auth -- this is inconsistent.

**Fix:** Add `current_user: CurrentUser = Depends(get_current_user)` to all four endpoints. Verify `tag.workspace_id == current_user.workspace_id` to prevent cross-workspace IDOR.

[FIXED in commit 005d3d7]

---

### MF-2 -- Tag PATCH endpoint only accepts `name`, frontend sends `name` + `color` [FIXED in commit 0f22d14]

**File (backend):** `backend/app/presentation/controllers/tag_controller.py:71-72` -- `RenameTagRequest` has only `name: str`
**File (frontend):** `frontend/components/admin/tag-edit-modal.tsx:52-56` -- `buildPatch()` sends `color`
**File (frontend):** `frontend/hooks/use-admin.ts:217` -- `archiveTag` sends `{ archived: true }` to PATCH

Two problems:
1. `TagEditModal.buildPatch()` sends `{ name, color }` but backend Pydantic model `RenameTagRequest` only has `name`. The `color` field is silently dropped. The user thinks they saved a color -- they did not.
2. `archiveTag` in `use-admin.ts:217` sends `{ archived: true }` to the PATCH endpoint which requires `name: str`. This will return 422 (required field missing). The archive button is broken.

**Fix (backend):** Rename `RenameTagRequest` to `UpdateTagRequest` with `name: str | None = None`, `color: str | None = None`, `archived: bool | None = None`. Update handler to apply changed fields. Or keep separate DELETE for archive and make PATCH accept `name` + `color`.
**Fix (frontend):** `archiveTag` should use `apiDelete` not `apiPatch` -- the backend has `DELETE /tags/{tag_id}` for archiving.

---

### MF-3 -- DomainError base class leaks `message` to clients on 500

**File:** `backend/app/domain/errors/codes.py:42-43` -- `DomainError.code` defaults to `INTERNAL_ERROR`
**File:** `backend/app/presentation/middleware/error_envelope.py:36-44`

When a `DomainError("something went wrong internally")` is raised, the envelope passes `exc.message` directly to the client with HTTP 500. For 500-class errors, the message should be a generic "Internal server error" -- never the developer-supplied string which may contain stack traces, SQL fragments, or internal service names.

**Fix:** In `_domain_error_handler`, when `exc.http_status >= 500`, replace `exc.message` with a generic string and log the real message server-side.

[FIXED in commit c39d8dc]

---

## Should Fix

### SF-1 -- Error code registry drift risk (Python/TS manual sync)

**File (Python):** `backend/app/domain/errors/codes.py:17-27`
**File (TS):** `frontend/lib/errors/codes.ts:10-20`

The comment says "manual sync required" and "consider codegen at ~50 codes." Currently 9 codes. TS has an extra `UNKNOWN` synthetic code. The Python `ERROR_CODES` dict also has `TAG_ARCHIVED` and `INVALID_INPUT` used in `tag_controller.py:146,151` but these are NOT in the registry -- they are inline strings in `HTTPException.detail`. This means the TS side has no way to match them.

**Fix:** Add `TAG_ARCHIVED` and `INVALID_INPUT` to both registries. Or, raise `DomainError` subclasses instead of `HTTPException` with inline codes in the tag controller.

[FIXED in commit cafaaf9 — controller now raises TagArchivedDomainError/InvalidInputError; both codes were already in registry]

---

### SF-2 -- `useFormErrors` replaces rather than merges field errors [FIXED in commit 5d34ee5]

**File:** `frontend/lib/errors/use-form-errors.ts:26`

`setFieldErrors({ [err.field]: err.message })` blows away any previous field errors. If the API ever returns a second field-level error before the user clears the form, only the last one survives. Currently the backend only sends one error per response, so this works, but it is a latent bug that will break the moment multi-field validation is added.

**Fix:** `setFieldErrors((prev) => ({ ...prev, [err.field]: err.message }))`.

---

### SF-3 -- Hydration mismatch in MatrixEntryCascade [FIXED in commit 3bef712]

**File:** `frontend/components/system/matrix-entry-cascade/matrix-entry-cascade.tsx:158`

```tsx
if (typeof window !== 'undefined' && prefersReducedMotion()) return null;
```

This runs during render. On the server, `window` is undefined so the branch is skipped and the component returns `<canvas>`. On the client with `prefers-reduced-motion: reduce`, it returns `null`. React will log a hydration mismatch warning. The `useEffect` path (line 78) correctly handles reduced motion -- this render-time check is redundant and harmful.

**Fix:** Remove line 158. The `useEffect` already handles reduced-motion (fires `onComplete` and never starts the RAF loop). The canvas will mount but stay blank, which is fine.

---

### SF-4 -- No workspace-scoping on tag PATCH/DELETE (even after auth is added)

**File:** `backend/app/presentation/controllers/tag_controller.py:128-171`

Even after MF-1 is fixed, the endpoints fetch a tag by `tag_id` alone without verifying it belongs to `current_user.workspace_id`. A user in workspace A can modify tags in workspace B.

**Fix:** After `repo.get(tag_id)`, assert `tag.workspace_id == current_user.workspace_id`.

[FIXED in commit 005d3d7 — _get_tag_scoped() checks workspace_id, returns 404 on violation]

---

### SF-5 -- `onComplete` in useEffect dependency array risks infinite loop [FIXED in commit 3bef712]

**File:** `frontend/components/system/matrix-entry-cascade/matrix-entry-cascade.tsx:155`

`onComplete` is in the dependency array of the canvas `useEffect`. If the parent doesn't memoize the callback, every render re-creates it, re-triggers the effect, and restarts the cascade in an infinite loop. The `UserMenu` component (line 81) passes an inline `() => setCascadeActive(false)` which is a new function reference every render.

**Fix:** Either wrap `onComplete` in `useRef` inside `MatrixEntryCascade`, or memoize the callback in `UserMenu` with `useCallback`.

---

### SF-6 -- Toast uses `text.textContent` but deduplication key is unsanitized [FIXED in commit 5340390]

**File:** `frontend/lib/errors/toast.ts:15`

`const dedupeKey = 'toast-${code}-${message}'` is used as an element ID. If `message` contains characters invalid in HTML IDs (spaces, quotes, angle brackets), `document.getElementById(dedupeKey)` may not find the element, breaking deduplication. This is not XSS (textContent is safe), but it means duplicate toasts can stack.

**Fix:** Hash or sanitize the dedupeKey: `const dedupeKey = 'toast-' + btoa(code + message).slice(0, 32)`.

---

### SF-7 -- Fake Dundun client in production code path

**File:** `backend/app/infrastructure/tasks/dundun_tasks.py:58`

```python
if settings.dundun.use_fake:
    from app.infrastructure.fakes.fake_dundun_client import FakeDundunClient
```

The import is conditional on a settings flag, which is fine for dev. But `FakeDundunClient` now lives in `app.infrastructure.fakes` (production package tree) rather than `tests/`. This means the fake is shipped with the production image. Not a security issue, but it bloats the image and someone will eventually flip `use_fake=True` in prod by accident.

**Fix:** Guard the import with an `APP_ENV != "production"` check, or keep the fake in `tests/` and let `dundun_tasks.py` import from there only in dev/test.

[FIXED in commit b654457]

---

## Nitpick

### N-1 -- Hardcoded Spanish UI strings in modals

**Files:** `frontend/components/work-item/work-item-edit-modal.tsx:29-46`, `frontend/components/admin/tag-edit-modal.tsx`

Priority labels (`Baja`, `Media`, `Alta`), type labels (`Error`, `Mejora`), and dialog titles (`Editar elemento`) are hardcoded in Spanish. The rest of the app uses `useTranslations()` (e.g., `user-menu.tsx:31`). These components bypass i18n.

---

### N-2 -- `as Priority` / `as WorkItemType` unsafe casts

**File:** `frontend/components/work-item/work-item-edit-modal.tsx:166,185`

`v as Priority` and `v as WorkItemType` are unchecked casts from `string`. If the Select component emits an unexpected value, these silently produce an invalid payload.

**Fix:** Validate with a type guard or a Set lookup before casting.

---

### N-3 -- `role="button"` on elements that are already `<button>`

**File:** `frontend/components/workspace/user-menu/user-menu.tsx:139,178`

`<button type="button" role="button">` -- the explicit `role="button"` is redundant on a `<button>` element.

---

### N-4 -- Unused `request` parameter in dundun-fake

**File:** `infra/dundun-fake/app.py:56`

`request: Request` is declared but never used in `post_message`.

---

### N-5 -- Seed script idempotency detection is fragile

**File:** `backend/scripts/seed_notifications.py:72`

```python
if existing.id == notification.id:
    created += 1
```

This relies on the repository returning the same object reference or a fresh UUID for new rows vs. the existing row for duplicates. If the repo implementation changes (e.g., returns a copy with a new id), the count will be wrong. Not a production concern, but worth documenting the contract.

---

## Solid Commits (no issues)

| Commit | Verdict |
|--------|---------|
| `5b9b2a4` PageContainer | Clean. Simple component, good responsive design, tested. |
| `6f0523f` Error envelope backend | Well-structured. DomainError hierarchy is clean. Registration order is correct (after generic handler). Tests cover all codes + envelope invariants. One issue: 500 message leakage (MF-3). |
| `59d8729` ApiError + field mapping frontend | Good. `parseErrorBody` handles both new envelope and legacy `{ detail }` shape. Tests cover all branches including malformed body. |
| `9278590` ColorPicker | Clean component. Keyboard nav, radiogroup semantics, debounced input, hex validation all correct. Tests are thorough (227 lines). |
| `64dab13` Dundun fake infra | Reasonable. Tests cover happy path + error injection + validation. |
| `082e2b4` Hook refresh fix (F-3) | `useTeams` now does optimistic local state update on create/delete and re-fetch on addMember. Pattern is consistent. `useTags.replaceTag` callback was added for edit modal integration. |

---

## Summary

| Severity | Count |
|----------|-------|
| Must Fix | 3 |
| Should Fix | 7 |
| Nitpick | 5 |

**Blocking:** MF-1 (unauthenticated tag mutation) and MF-2 (broken archive + silent color drop) must be fixed before merge. MF-3 (500 message leakage) should be fixed before any production deployment.
