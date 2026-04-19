# DB Review — Session 2026-04-17

Range: `8ffcd2d..HEAD` (24 commits). DB-touching changes only.

---

## Must Fix

### MF-1: N+1 in `list_teams` — `_resolve_members` called per team

**File:** `backend/app/presentation/controllers/team_controller.py:160-163`

```python
for t in teams:
    members = await _resolve_members(session, t.id)
    payloads.append(_team_payload(t, members=members))
```

One query per team. 20 teams = 20 round-trips. Replace with a single batch query:

```sql
SELECT tm.*, u.*
FROM team_memberships tm
JOIN users u ON tm.user_id = u.id
WHERE tm.team_id = ANY(:team_ids)
  AND tm.removed_at IS NULL
ORDER BY tm.joined_at ASC
```

Then group by `team_id` in Python. Single query, no loop.

---

### MF-2: Missing index on `team_memberships(team_id)` for the member-resolve join

**File:** `backend/migrations/versions/0025_create_teams_notifications.py`

The only index on `team_memberships` is `idx_team_memberships_user_active(user_id) WHERE removed_at IS NULL`. The `_resolve_members` query filters on `team_id` + `removed_at IS NULL` — that index does not cover it. The `uq_team_membership_active(team_id, user_id)` unique constraint gives an index on `(team_id, user_id)`, which covers the `team_id` filter but not the `removed_at IS NULL` predicate efficiently.

Add a partial composite index:

```sql
CREATE INDEX idx_team_memberships_team_active
ON team_memberships(team_id, joined_at)
WHERE removed_at IS NULL;
```

This covers the exact WHERE + ORDER BY of `_resolve_members`.

---

### MF-3: ORM `_WORK_ITEM_TYPES` constant out of sync with migration 0031

**File:** `backend/app/infrastructure/persistence/models/orm.py:207-209`

```python
_WORK_ITEM_TYPES = (
    "'idea','bug','enhancement','task','initiative','spike','business_change','requirement'"
)
```

Migration 0031 adds `story` and `milestone` to the CHECK constraint in the database, but the ORM-level constant (used by `__table_args__` on `WorkItemORM`) is stale. SQLAlchemy metadata introspection / autogenerate will see a drift. Any code path relying on this constant for validation is broken for the new types.

Update to include `'story','milestone'`.

---

### MF-4: Migration 0031 downgrade will fail if rows with `type='story'` or `type='milestone'` exist

**File:** `backend/migrations/versions/0031_extend_work_item_types.py:30-36`

The downgrade blindly re-creates the old CHECK constraint. If any work item has `type='story'` or `type='milestone'`, the `ADD CONSTRAINT` will fail with a check violation. The downgrade must either:

1. DELETE/UPDATE offending rows first (risky — data loss), or
2. Add the constraint `NOT VALID` (allows existing violations but enforces on new inserts), or
3. Document that downgrade requires manual data migration.

Option 2 is safest if you just want to roll back the code:

```sql
ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid
    CHECK (type IN (...)) NOT VALID;
```

---

## Should Fix

### SF-1: `GET /workspaces/members` returns unbounded results — no LIMIT, no pagination

**File:** `backend/app/presentation/controllers/workspace_controller.py:75-123`

A workspace with 500+ members (possible in enterprise) will dump everything in one response. Add at minimum a `LIMIT 200` default with cursor/offset pagination.

The same pattern repeats in:
- `list_projects` (`project_controller.py:97-108`) — no LIMIT
- `list_teams` (`team_controller.py:148-164`) — no LIMIT
- `list_for_workspace` on templates (`template_repository_impl.py:117-122`) — no LIMIT

All of these are currently fine for small workspaces but will degrade as data grows. Add pagination system-wide.

---

### SF-2: `project_controller.create_project` catches bare `IntegrityError` — masks FK violations

**File:** `backend/app/presentation/controllers/project_controller.py:83-93`

```python
except IntegrityError as exc:
    raise HTTPException(
        status_code=http_status.HTTP_409_CONFLICT,
        detail={...  "code": "PROJECT_NAME_TAKEN" ...}
    )
```

`IntegrityError` can fire for any constraint: FK violation on `workspace_id`, unique on `(workspace_id, name)`, or any future constraint. Inspecting `exc.orig.pgcode` or `exc.orig.diag.constraint_name` to distinguish unique violations (`23505`) from FK violations (`23503`) is the correct approach. Otherwise a bad `workspace_id` returns "project name taken" — misleading and a debugging nightmare.

---

### SF-3: `team_controller.get_team` and `project_controller.get_project` do not verify workspace ownership

**Files:**
- `backend/app/presentation/controllers/team_controller.py:167-187`
- `backend/app/presentation/controllers/project_controller.py:111-129`

`service.get(team_id)` / `service.get(project_id)` fetches by PK only (`session.get(ORM, id)`). There is no RLS on the `teams` or `projects` table (RLS is only on `work_items`, `state_transitions`, `ownership_history`). A user in workspace A can fetch teams/projects belonging to workspace B by guessing UUIDs. The scoped session sets `app.current_workspace` but that GUC is never checked by `teams` or `projects` — no RLS policy exists.

Fix: either add RLS policies on `teams` and `projects`, or add a `workspace_id` filter in the repository `.get()` methods.

---

### SF-4: `InMemoryCacheAdapter` has no size bound — unbounded memory growth

**File:** `backend/app/infrastructure/adapters/in_memory_cache_adapter.py`

No max-size, no eviction policy. In a long-running dev server, every unique cache key accumulates forever (expired entries only purged on read-hit). This is fine for short test runs but will leak in a dev server left running. Add a simple max-entries check in `set()` with LRU eviction, or at minimum a periodic sweep.

---

### SF-5: `_IN_MEMORY_CACHE` module global is not worker-safe and leaks across tests

**File:** `backend/app/presentation/dependencies.py:257-275`

```python
_IN_MEMORY_CACHE: ICache | None = None
```

1. **Multi-worker**: Under gunicorn with multiple workers, each worker forks and gets its own `_IN_MEMORY_CACHE`. Cache is per-process, not shared. This is fine for dev but must never reach prod — it silently degrades to no-cache behavior (cache misses on every request that hits a different worker).

2. **Test isolation**: The global is never reset between test cases. If test A writes a cache entry and test B reads it, you get order-dependent test results. Tests should override `get_cache_adapter` per-test (which they likely do), but the fallback global is a footgun.

---

### SF-6: Migration 0031 — `ADD CONSTRAINT` acquires `ACCESS EXCLUSIVE` lock under concurrent writes

**File:** `backend/migrations/versions/0031_extend_work_item_types.py:21-27`

`ALTER TABLE ... ADD CONSTRAINT ... CHECK (...)` takes an `ACCESS EXCLUSIVE` lock while validating existing rows. On a large `work_items` table this blocks all reads and writes until validation completes.

Safe pattern:

```sql
ALTER TABLE work_items ADD CONSTRAINT work_items_type_valid
    CHECK (type IN (...)) NOT VALID;
ALTER TABLE work_items VALIDATE CONSTRAINT work_items_type_valid;
```

`NOT VALID` acquires `ACCESS EXCLUSIVE` only briefly (no full-table scan). `VALIDATE CONSTRAINT` acquires `SHARE UPDATE EXCLUSIVE` — reads and writes continue. Two-step is the standard for zero-downtime migrations.

This is "should fix" rather than "must fix" only because this appears to be an internal tool with controlled deployment windows. For any internet-facing or high-traffic table, this would be must-fix.

---

## Nitpick

### N-1: `workspace_controller` opens its own session instead of using DI

**File:** `backend/app/presentation/controllers/workspace_controller.py:40-41, 89`

```python
factory = get_session_factory()
async with factory() as session:
```

Every other controller uses `Depends(get_db_session)` or `Depends(get_scoped_session)`. This controller manually instantiates sessions, bypassing the transaction boundary in `get_db_session` (auto-commit/rollback). The `list_workspace_members` endpoint should use the scoped session for consistency and to benefit from any future middleware (metrics, tracing, etc.).

---

### N-2: `access_token_ttl_seconds` bumped from 15 min to 7 days

**File:** `backend/app/config/settings.py:55`

```python
access_token_ttl_seconds: int = 604_800      # 7 days — internal tool, low risk
```

The comment says "internal tool, low risk" but a 7-day access token is a 7-day window where a stolen token grants full access with no server-side revocation check (JWT is stateless). If the refresh token flow works correctly, access tokens should stay short (15-30 min) and refreshes should be frequent. The 7-day TTL effectively makes the access token a session token, negating the access/refresh split entirely.

Not a DB issue per se, but it affects the auth/session surface area.

---

### N-3: `rate_limit_per_minute` bumped from 10 to 300

**File:** `backend/app/config/settings.py:58`

300 req/min per IP on auth endpoints is generous. Fine for an internal tool behind a VPN. If this ever becomes internet-facing, tighten to 20-30 for auth endpoints specifically.

---

## Summary

| Severity | Count | Key themes |
|----------|-------|------------|
| Must Fix | 4 | N+1 query, missing index, ORM/migration drift, unsafe downgrade |
| Should Fix | 6 | No pagination, IDOR on teams/projects, IntegrityError masking, cache unbounded, lock safety |
| Nitpick | 3 | Session DI bypass, token TTL, rate limit |
