# Session Code Review — 2026-04-17

**Range:** `8ffcd2d..HEAD` (24 commits, ~1900 LOC)
**Reviewer:** code-reviewer (Opus)

---

## Must Fix

### MF-1. JWT access_token_ttl_seconds: 15 min to 7 days — security regression

`backend/app/config/settings.py:55`

```python
access_token_ttl_seconds: int = 604_800  # 7 days — internal tool, low risk
```

This is not low risk. Access tokens are stateless — once issued they cannot be revoked until expiry. A leaked token (XSS, log, clipboard, browser extension) gives 7 full days of access. The refresh token is already 30 days for session continuity; the access token is supposed to be short-lived precisely so that revocation is "eventual" on a short horizon.

"Internal tool" is not a threat model. Internal tools get compromised. The comment even says "tighten if exposed" — which means the author knows this is wrong and is deferring the fix.

**Recommendation:** Revert to 15 min (or at most 1h). If the DX complaint is "too many refreshes during dev", use `dev_token.py` (which already mints 8h tokens) or set the override via env var in `.env.development` only. Do not ship 7-day access tokens as the default.

### MF-2. Rate limit 10 to 300 on /auth/* — brute-force surface

`backend/app/config/settings.py:57`

```python
rate_limit_per_minute: int = 300  # slowapi: 300 req/min per IP on /auth/*
```

300 req/min on auth endpoints (login, refresh, OAuth initiate) is effectively no rate limit. At 5 req/sec an attacker can probe credentials, abuse refresh, or generate thousands of OAuth states. The original 10/min was already generous for legitimate auth flows.

**Recommendation:** Revert to 10-20/min. If the dev workflow needs more (e.g. automated test suite hammering refresh), override via env var in dev only.

### MF-3. `assert` used for authorization checks — stripped by `python -O`

`backend/app/presentation/controllers/template_controller.py:63` (and 16 more instances across `template_controller.py` and `work_item_controller.py`)

```python
assert current_user.workspace_id is not None
```

`assert` statements are removed when Python runs with `-O` or `-OO` (optimized bytecodes). If anyone ever runs the backend with `PYTHONOPTIMIZE=1` or `python -O`, every single workspace_id check evaporates. This is a real deployment footgun.

The `work_item_controller.py` comments say "guaranteed by get_scoped_session" but the `template_controller.py` endpoints do NOT use `get_scoped_session` — they only depend on `get_current_user`, which does NOT enforce workspace_id presence. So the assert is the ONLY guard, and it is unreliable.

**Recommendation:** Replace every `assert current_user.workspace_id is not None` with:
```python
if current_user.workspace_id is None:
    raise HTTPException(status_code=401, detail={"error": {"code": "NO_WORKSPACE", ...}})
```
Or add `get_scoped_session` as a dependency to those endpoints (it already does the check properly).

### MF-4. N+1 query in `list_teams` — `_resolve_members` runs per team

`backend/app/presentation/controllers/team_controller.py:157-159`

```python
for t in teams:
    members = await _resolve_members(session, t.id)
    payloads.append(_team_payload(t, members=members))
```

One query per team. A workspace with 50 teams fires 51 queries (1 list + 50 member resolves). This is textbook N+1, in the presentation layer no less.

**Recommendation:** Single query joining `TeamMembershipORM` + `UserORM` for all team IDs at once, then group in Python. Or push this into the service layer where it belongs (the controller is currently importing ORM models directly — architecture violation).

### MF-5. Team controller imports ORM models in presentation layer

`backend/app/presentation/controllers/team_controller.py:31-34`

```python
from app.infrastructure.persistence.models.orm import (
    TeamMembershipORM,
    UserORM,
)
```

Controller depends on infrastructure. This violates DDD layering (presentation -> infrastructure, skipping application/domain). The controller also takes `AsyncSession` directly via `get_scoped_session`. Raw SQL in controllers is the same anti-pattern as business logic in controllers.

**Recommendation:** Move `_resolve_members` logic into `TeamService` (application layer). The service already owns team queries — member resolution belongs there. Same applies to `workspace_controller.py` which also queries ORM directly.

### MF-6. `dev_token.py` has no environment guard

`backend/scripts/dev_token.py`

The script mints arbitrary JWT tokens for any user. It has a docstring saying "Local dev only" but zero runtime enforcement. If `settings.py` can load (i.e. env vars are set), this script will happily mint tokens against a production database.

**Recommendation:** Add an environment check at the top of `run()`:
```python
if os.environ.get("ENVIRONMENT", "production") not in ("development", "test", "local"):
    print("[dev-token] REFUSED: not a dev environment", file=sys.stderr)
    return 1
```

---

## Should Fix

### SF-1. GET /workspaces/members — no pagination, no authorization scope check

`backend/app/presentation/controllers/workspace_controller.py:75-123`

The endpoint returns ALL active members with email + avatar_url + role for the entire workspace. No pagination, no limit. A workspace with 10,000 members dumps all of them in one response.

Privacy angle: every workspace member can see every other member's email. Depending on the product (B2B internal tool vs. multi-tenant SaaS), this might be fine or might be a data leak. Document the decision either way.

**Recommendation:** Add `LIMIT` (default 100, max 500) + offset/cursor. Even if "workspaces are small today", unbounded queries are a time bomb.

### SF-2. GET /workspaces/members and list_teams — no authorization beyond "has workspace"

Both endpoints return data for any authenticated user with a workspace_id. There is no role check — a `viewer` role member sees the same data as an `admin`. This is probably intentional for picker UIs but should be explicitly documented or enforced.

### SF-3. Session-expired modal hardcodes Spanish strings

`frontend/components/auth/session-expired-modal.tsx:41-45`

```tsx
<DialogTitle>Tu sesión ha caducado</DialogTitle>
<DialogDescription>
  Por seguridad, necesitas iniciar sesión de nuevo...
</DialogDescription>
```

The entire session just migrated everything to `next-intl`. This modal was added in the same session and doesn't use `useTranslations`. Inconsistent and broken for English-only users.

**Recommendation:** Add keys to `locales/en.json` and `locales/es.json`, use `useTranslations()`.

### SF-4. Orphaned EP-20 components: `RedPill`, `BluePill`, `RainToggle` are unused in production code

These components are imported only in their own test files. The user-menu (EP-21 F-7) encodes theme switching directly via `ThemeSwitcher`, bypassing RedPill/BluePill entirely. `RainToggle` is never imported outside its own module.

- `MatrixRain` IS used (in `workspace-sidebar.tsx`)
- `ThemeSwitcher` IS used (re-exported as `ThemeToggle`)
- `RedPill`, `BluePill`, `RainToggle` are dead code

**Recommendation:** Either wire them into the UI or delete them. Shipped dead code with tests is maintenance cost for zero value. If they are "planned for later", add a TODO with a ticket reference.

### SF-5. `PROJECT_NAME_TAKEN` error code not in `ERROR_CODES` registry

`backend/app/presentation/controllers/project_controller.py:84-91`

The controller catches `IntegrityError` and returns `PROJECT_NAME_TAKEN` as the error code, but this code is not registered in `backend/app/domain/errors/codes.py`. The error code registry exists for consistency and for the global error handler to map codes to HTTP statuses. A raw `IntegrityError` catch in the controller (instead of a domain error from the service) also bypasses the domain error pattern.

**Recommendation:** Add `"PROJECT_NAME_TAKEN": 409` to `ERROR_CODES`. Better: catch the IntegrityError in `ProjectService`, raise a `ProjectNameTakenError(DomainError)`, and let the global handler map it.

### SF-6. Migration 0031 — `DROP CONSTRAINT` + `ADD CONSTRAINT` is not concurrent-safe

`backend/migrations/versions/0031_extend_work_item_types.py:23-27`

```python
op.execute("ALTER TABLE work_items DROP CONSTRAINT IF EXISTS work_items_type_valid")
op.execute("ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid CHECK (...)")
```

`ADD CONSTRAINT ... CHECK` on PostgreSQL acquires an `ACCESS EXCLUSIVE` lock on the table. On a large `work_items` table, this blocks all reads and writes for the duration of the constraint validation scan.

PostgreSQL 9.2+ supports `ALTER TABLE ... ADD CONSTRAINT ... NOT VALID` followed by `ALTER TABLE ... VALIDATE CONSTRAINT` which only takes a `SHARE UPDATE EXCLUSIVE` lock (allows reads, blocks writes only briefly).

The downgrade path also drops and recreates, which will fail if any `story`/`milestone` rows exist. No data migration, no check.

**Recommendation:** Use `NOT VALID` + `VALIDATE CONSTRAINT` pattern. Add a guard in downgrade that checks for rows with new types before recreating the old constraint.

### SF-7. `list_for_workspace` (template service) bypasses cache

`backend/app/application/services/template_service.py:71-72`

The existing `get_template_for_type` method uses the cache. The new `list_for_workspace` hits the repo directly. If templates are cached for single lookups, the list endpoint should at minimum be consistent. A list-all that bypasses cache while single-get uses cache leads to stale-vs-fresh inconsistencies.

**Recommendation:** Either cache the list too, or document why it is intentionally uncached.

### SF-8. i18n test mocks — duplicated `vi.mock('next-intl', ...)` in 13+ test files

Every test file that renders a component with translations has its own copy of the `next-intl` mock. Same factory function, same shape, duplicated 13 times. When the mock shape changes (and it will — e.g. `useLocale` was added in some files), you update one and forget the others.

**Recommendation:** Extract to `__tests__/helpers/mock-intl.ts` and import it. Or use vitest's `setupFiles` to auto-mock globally.

---

## Nitpick

### N-1. `window.location.href` in session-expired modal — intentional but undocumented

`frontend/components/auth/session-expired-modal.tsx:27`

```tsx
window.location.href = `/api/v1/auth/google?return_to=${encodeURIComponent(returnTo)}`;
```

The comment says "evita el paso extra por /login" (avoid the extra step through /login). Using `window.location.href` instead of `router.push` is correct here because the target is a backend endpoint (OAuth redirect), not a Next.js route. The `return_to` value is validated server-side by `_safe_return_to()` which blocks open redirects (protocol-relative, scheme, userinfo). This is fine.

The only gap: `return_to` is URL-encoded on the frontend but `_safe_return_to` validates the raw value after the backend's query-string parser decodes it. The chain is correct — just noting it for future reference.

### N-2. Type guards `isPriority` / `isWorkItemType` — correct but fragile

`frontend/components/work-item/work-item-edit-modal.tsx:43-45`

The guards cast `readonly Priority[]` to `readonly string[]` before calling `.includes()`. This is correct TypeScript — `Array<T>.includes()` requires the argument type to match, and `string` is wider than `Priority`. The cast is the standard workaround.

The fragility: `TYPE_VALUES` and `PRIORITY_VALUES` are manually maintained arrays. If someone adds a new type to `WorkItemType` (the union) but forgets to add it to `TYPE_VALUES`, the guard silently rejects valid values. Consider deriving the array from the type or adding a compile-time exhaustiveness check.

### N-3. Smoke test mock for `redirect` throws generic `Error('NEXT_REDIRECT')`

`frontend/__tests__/smoke.test.tsx:7-10`

```tsx
redirect: (url: string) => {
  redirectMock(url);
  throw new Error('NEXT_REDIRECT');
},
```

Next.js `redirect()` throws a special `NEXT_REDIRECT` error type (not a plain `Error`). The test works because it catches by message, but if any code ever checks `instanceof`, this mock will behave differently. Low risk for a smoke test, but worth noting.

### N-4. `InMemoryCacheAdapter` — uses module-level global singleton

`backend/app/presentation/dependencies.py:257-264`

```python
_IN_MEMORY_CACHE: ICache | None = None
```

The singleton is stored as a module global, which means it persists across requests in the same process. This is the intended behavior for a dev cache, but it also means tests using `REDIS_USE_FAKE=true` share cache state across test cases. Could cause flaky tests if test isolation is not careful.

### N-5. `template_controller.py:68` — inline import of `HTTPException`

```python
from fastapi import HTTPException
```

`HTTPException` is already imported at the top of the file (line 6 area). This inline import is dead weight — probably a copy-paste artifact.

### N-6. `dev.sh` is fine

Reviewed the launcher script. It is local-only, requires manual invocation, and does not touch production resources. No concerns.

---

## Summary

| Severity | Count | Key themes |
|----------|-------|------------|
| Must Fix | 6 | JWT TTL regression, rate limit gutted, assert-as-auth, N+1, layer violation, dev script unsafe |
| Should Fix | 8 | Unbounded queries, hardcoded Spanish, dead code, missing error code, migration locking, cache inconsistency, mock duplication |
| Nitpick | 6 | Correct but fragile patterns, inline imports, test mock fidelity |

The session shipped a lot of useful work. The API type sync, cursor pagination migration, and session-expired flow are solid. The `_safe_return_to` open-redirect protection is well done. The core problems are: (1) security defaults loosened for dev convenience and shipped as production defaults, (2) presentation layer doing infrastructure work, and (3) the `assert` pattern for auth checks which is a real deployment risk.
