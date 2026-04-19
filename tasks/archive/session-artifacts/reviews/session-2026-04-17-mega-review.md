# Mega Session Review -- 2026-04-17

Reviewer: Hawking (code-reviewer, read-only)
Scope: commits `8ffcd2d..HEAD` (152 commits, EP-01 through EP-14+)

---

## Must Fix

### MF-1: RLS missing on 8 workspace-scoped tables

Tables with `workspace_id NOT NULL` but **no** `ENABLE ROW LEVEL SECURITY` or `CREATE POLICY`:

| Table | Migration | workspace_id | RLS |
|-------|-----------|:---:|:---:|
| `teams` | 0025 | YES | NO |
| `notifications` | 0025 | YES | NO |
| `saved_searches` | 0026 | YES | NO |
| `projects` | 0027 | YES | NO |
| `routing_rules` | 0027 | YES | NO |
| `integration_configs` | 0027 | YES | NO |
| `integration_exports` | 0028 | YES | NO |
| `validation_rule_templates` | 0111 | YES | NO |
| `work_item_drafts` | 0012 | YES | NO |

Tables **with** RLS: `work_items`, `state_transitions`, `ownership_history` (0009), `conversation_threads`, `assistant_suggestions`, `gap_findings` (0033), `puppet_ingest_requests` (0034).

**Impact**: Any user in any workspace can read/write teams, notifications, saved searches, projects, routing rules, integration configs, and validation rule templates belonging to other workspaces -- if the application-level scoped session (`with_workspace`) fails or is bypassed. Defense in depth is broken.

**Action**: Add a migration (`0112_rls_backfill.py`) that does `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY <table>_workspace_isolation` on each. Same pattern as 0009/0033/0034.

### MF-2: `task_controller.py` + `suggestion_controller.py` -- zero workspace_id guards

Neither controller has `workspace_id is None` checks OR `get_scoped_session` dependency on any endpoint. Every other controller in the codebase checks this.

- `backend/app/presentation/controllers/task_controller.py` -- 18 endpoints, 0 guards
- `backend/app/presentation/controllers/suggestion_controller.py` -- 5 endpoints, 0 guards

These controllers take `get_current_user` but never validate workspace presence. A token without `workspace_id` would hit the service layer unscoped.

**Why it matters**: IDOR risk. Without workspace scoping, task/suggestion operations can cross workspace boundaries.

### MF-3: `dundun_callback_controller.py:229` hardcodes `version_number_target=1`

```python
version_number_target=1,  # TODO EP-07: fetch current version from work_item
```

Any callback from Dundun for a work item past version 1 will target the wrong version. This will silently corrupt versioned sections.

**File**: `backend/app/presentation/controllers/dundun_callback_controller.py:229`

### MF-4: `validation_controller.py:72` hardcodes work_item.type to empty string

```python
# TODO: fetch work_item.type -- for now default to "" (matches all rules)
```

The validation seeding matches ALL rules regardless of work item type. When the DB accumulates type-specific rules, every work item will get every rule.

**File**: `backend/app/presentation/controllers/validation_controller.py:72`

---

## Should Fix

### SF-1: FE test flake -- `request-review-dialog-version-id.test.tsx`

2 tests fail in full suite run but pass in isolation. Classic test pollution. The MSW `onUnhandledRequest: "error"` strategy catches leaking handlers from a prior test file. The test file imports `server` from `@/__tests__/msw/server` but upstream tests leave stale handlers.

**File**: `frontend/__tests__/components/work-item/request-review-dialog-version-id.test.tsx`
**Impact**: CI red. 2 failed / 911 total.

### SF-2: Hardcoded Spanish strings in FE (i18n miss)

At least 7 hardcoded Spanish strings survived the i18n migration:

- `frontend/app/workspace/[slug]/teams/page.tsx:224` -- `"Nombre del equipo"`
- `frontend/app/workspace/[slug]/teams/page.tsx:234` -- `"Descripcion opcional"`
- `frontend/app/workspace/[slug]/teams/page.tsx:280` -- `"Selecciona un miembro del workspace"`
- `frontend/app/workspace/[slug]/items/new/page.tsx:285` -- `"Titulo del elemento"`
- `frontend/app/workspace/[slug]/items/new/page.tsx:299` -- `"Selecciona un tipo"`
- `frontend/app/workspace/[slug]/items/new/page.tsx:416,467` -- `"Descripcion opcional"`
- `frontend/app/workspace/[slug]/admin/page.tsx:449` -- `"Descripcion opcional"`
- `frontend/components/work-item/work-item-header.tsx:114` -- `aria-label="Titulo del elemento"`

### SF-3: Middleware TODO -- 4 middlewares created but not wired

EP-12 created 4 middleware classes each with `# TODO: EP-12 phase 9 -- wire in main.py`:

- `backend/app/presentation/middleware/security_headers.py:14`
- `backend/app/presentation/middleware/body_size_limit.py:16`
- `backend/app/presentation/middleware/cors_policy.py:14`
- `backend/app/presentation/middleware/request_logging.py:10`

Commit `6a4d1c4` claims "wire EP-12 middleware chain into app startup" but the TODO comments remain in the files. Verify if `main.py` actually mounts them or if the wiring is incomplete.

### SF-4: Puppet HTTP client -- 3 endpoints are no-op stubs

```
backend/app/infrastructure/adapters/puppet_http_client.py:29  # TODO: replace with real paths
backend/app/infrastructure/adapters/puppet_http_client.py:86  # TODO: Puppet platform-ingestion PENDING
backend/app/infrastructure/adapters/puppet_http_client.py:108 # TODO: Puppet DELETE PENDING
```

`upsert_document()` and `delete_document()` are stubs. Any code path that calls them (EP-13 sync) will silently succeed without actually syncing.

### SF-5: `completeness_service.py` + `work_item.py` -- scoring is TODO stub

```
backend/app/domain/models/work_item.py:201   # TODO(EP-04): implement scoring
backend/app/domain/services/completeness_service.py:12  # TODO(EP-04): implement scoring
```

The completeness endpoint exists and is wired to FE, but returns unimplemented scoring. The FE types correctly expect 0-100 int.

### SF-6: Cross-lane commit `1004dee` (EP-14 agent touched EP-07 files)

Commit `1004dee` (EP-14: DependencyManageDialog) modified:
- `frontend/components/work-item/timeline-tab.tsx` (EP-07 owned)
- `frontend/components/work-item/timeline-event-item.tsx` (EP-07 owned)
- `frontend/__tests__/components/work-item/timeline-tab.test.tsx` (EP-07 owned)

Changes look benign (likely just imports or re-exports) but violates lane discipline.

### SF-7: `routing_rule_controller.py` + `validation_rule_template_controller.py` -- rely on `require_admin` but no explicit workspace_id guard

Both controllers use `Depends(require_admin)` which presumably checks workspace, but there's no explicit `workspace_id is None` check like every other controller. If `require_admin` doesn't validate workspace presence, these are open.

---

## Nitpick

### NP-1: Migration file numbering gap

Sequence jumps: `0034 -> 0060 -> 0080 -> 0100 -> 0110 -> 0111`. The gaps are intentional (namespace reservation) but worth documenting. No orphans; `down_revision` chain is unbroken and all revision IDs are <= 30 chars (max was 30: `0110_ep10_routing_rules_active`). VARCHAR(32) constraint is satisfied.

### NP-2: `# type: ignore[arg-type]` scattered in routing_rule_controller

Lines 88, 99, 119, 136, 156 all have `# type: ignore[arg-type]` for `current_user.workspace_id`. This is because `CurrentUser.workspace_id` is `Optional[UUID]` but the service expects `UUID`. The proper fix is the missing workspace guard (SF-7).

### NP-3: ORM placeholder RLS comment

`backend/app/infrastructure/persistence/models/orm.py:1221`:
```python
"workspace_id IS NULL OR true",  # placeholder -- global templates allowed
```

This `OR true` makes the check constraint a no-op. Either enforce it or remove it.

### NP-4: 3 untracked files in working tree

```
?? frontend/__tests__/components/notifications/inbox-filter-bar.test.tsx
?? frontend/components/notifications/inbox-filter-bar.tsx
?? frontend/components/ui/sheet.tsx
```

Likely EP-08 FE scaffolding. Safe to commit or delete.

---

## Health Metrics

| Metric | Value |
|--------|-------|
| Total commits (8ffcd2d..HEAD) | 152 |
| Migration count | 38 files |
| Highest revision ID length | 30 chars (`0110_ep10_routing_rules_active`) -- safe for VARCHAR(32) |
| Migration chain | Unbroken. No orphans. |
| New services shipped | 38 (in `backend/app/application/services/`) |
| New controllers shipped | 34 (in `backend/app/presentation/controllers/`) |
| FE tests | 911 total, 909 pass, 2 flake |
| FE test files | 132 |
| BE unit tests | 1293 pass, 1 skip, 0 fail |
| BE test files | 156 (unit) + 47 (integration) |
| BE coverage (unit) | 51% |
| Untracked files | 3 (FE scaffolding) |
| Modified tracked (uncommitted) | 5 (AGENTS.md, CLAUDE.md, apm.lock.yaml, tasks/AGENTS.md, tasks/CLAUDE.md) |
| Event subscribers registered | 3 (timeline, notification, validation_template) -- all wired in `register_event_subscribers()` |
| DI consistency | `get_section_service` wires VersioningService correctly. `get_work_item_service` injects ReadyGate. No circular imports detected (all heavy imports deferred via `TYPE_CHECKING` or function-local). |

### MVP Completion Estimate (active EPs, excluding cuts EP-11/16/17/18)

| EP | BE done/total | FE done/total | % |
|----|:---:|:---:|:---:|
| EP-00 | 99/100 | 28/28 | 99% |
| EP-01 | 71/72 | 89/92 | 98% |
| EP-02 | 57/58 | 23/36 | 85% |
| EP-03 | 61/80 | 23/60 | 60% |
| EP-04 | 59/90 | 19/22 | 70% |
| EP-05 | 17/112 | 0/58 | 10% |
| EP-06 | 60/82 | 30/50 | 68% |
| EP-07 | 65/81 | 17/55 | 60% |
| EP-08 | 23/97 | 0/65 | 14% |
| EP-09 | 20/76 | 0/108 | 11% |
| EP-10 | 29/174 | 18/123 | 16% |
| EP-12 | 16/84 | 0/81 | 10% |
| EP-13 | 25/101 | 0/57 | 16% |
| EP-14 | 8/133 | 11/103 | 8% |
| EP-15 | 0/63 | 0/49 | 0% |
| EP-19 | -- | 49/59 | 83% |
| EP-20 | -- | 37/44 | 84% |
| EP-21 | -- | 26/27 | 96% |
| **Weighted total** | **610/1303** | **370/1117** | **~40%** |

**Estimated remaining MVP: ~40% complete across active EPs.**

EP-00/01/02/19/20/21 are nearly done. EP-05/08/09/10/12/13/14/15 are early. The bulk of remaining work is FE implementation for EPs 03-10 and all of EP-05/15 backend.
