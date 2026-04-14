# EP-10 — Technical Design
## Configuration, Projects, Rules & Administration

**Epic**: EP-10
**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Date**: 2026-04-13

---

## 1. Capability-Based Permission Model

### Decision: Capability Set per Member (Not RBAC)

The permission matrix is a capability matrix with named profiles as column headers, not system roles. No roles table, no role-permission join, no role-editor UI, no custom roles (resolution #10, #31).

**Five workspace profiles as code constants** (Member, Team Lead, Project Admin, Integration Admin, Workspace Admin) — each profile maps to a fixed capability set. **Superadmin** is a platform-level flag on `users.is_superadmin`, NOT a workspace profile.

**Storage**: `workspace_memberships.capabilities text[]` — resolved from the member's assigned profile at creation and refreshed when profile changes. The profile enum is also stored for display (`workspace_memberships.profile`).

```sql
-- No roles table. No role-permission join table.
-- Just a capabilities array on the member.
ALTER TABLE workspace_memberships ADD COLUMN capabilities text[] NOT NULL DEFAULT '{}';

-- Per db_review.md MS-3: GIN index creation takes ACCESS EXCLUSIVE lock.
-- Use CONCURRENTLY so it can run post-launch without blocking writes.
-- NOTE: CONCURRENTLY cannot run inside a transaction block — Alembic migration
-- must set `transactional_ddl = False` for this step or wrap in `op.execute()`
-- with an explicit autocommit connection.
CREATE INDEX CONCURRENTLY idx_workspace_memberships_capabilities
    ON workspace_memberships USING GIN (capabilities);
```

Capability strings are an enumerated set defined in application code:
```python
class Capability(str, Enum):
    INVITE_MEMBERS = "invite_members"
    DEACTIVATE_MEMBERS = "deactivate_members"
    MANAGE_TEAMS = "manage_teams"
    CONFIGURE_WORKSPACE_RULES = "configure_workspace_rules"
    CONFIGURE_PROJECT = "configure_project"
    CONFIGURE_INTEGRATION = "configure_integration"
    VIEW_AUDIT_LOG = "view_audit_log"
    VIEW_ADMIN_DASHBOARD = "view_admin_dashboard"
    REASSIGN_OWNER = "reassign_owner"
    RETRY_EXPORTS = "retry_exports"
    FORCE_UNLOCK = "force_unlock"            # workspace admin + superadmin; delegates to EP-17
    MANAGE_TAGS = "manage_tags"              # tag CRUD (EP-15 implementation)
    MERGE_TAGS = "merge_tags"               # tag merge — higher bar, workspace admins only
    MANAGE_PUPPET_INTEGRATION = "manage_puppet_integration"  # workspace admin
```

### Superadmin Short-Circuit

`is_superadmin` on `users` is a platform-level flag — it crosses workspace boundaries. Superadmin bypasses all capability checks. The `require_capabilities` dependency short-circuits immediately if `user.is_superadmin = true`. Workspace membership state check is still applied (a superadmin whose membership is suspended still gets blocked by `WorkspaceMemberMiddleware` for in-workspace actions, but cross-workspace endpoints use `require_superadmin` instead).

```python
async def check(member: WorkspaceMember = Depends(get_current_member)):
    if member.user.is_superadmin:
        return member          # bypasses all capability checks
    if member.state != MemberState.ACTIVE:
        raise InactiveMemberError()
    missing = set(caps) - set(member.capabilities)
    if missing:
        raise CapabilityRequiredError(missing)
    return member
```

### Capability Check Middleware

FastAPI dependency, not a decorator, to keep it testable:

```python
def require_capabilities(*caps: Capability) -> Depends:
    async def check(member: WorkspaceMember = Depends(get_current_member)):
        if member.state != MemberState.ACTIVE:
            raise InactiveMemberError()
        missing = set(caps) - set(member.capabilities)
        if missing:
            raise CapabilityRequiredError(missing)
        return member
    return Depends(check)
```

Usage: `@router.post(..., dependencies=[require_capabilities(Capability.INVITE_MEMBERS)])`

### Capability Granting Constraint

A member can only grant capabilities they themselves hold. Enforced in the service layer:

```python
def grant_capabilities(actor: WorkspaceMember, target_member_id: UUID, to_grant: list[Capability]):
    unpossessed = set(to_grant) - set(actor.capabilities)
    if unpossessed:
        raise CannotGrantUnpossessedCapabilityError(unpossessed)
```

### Default Capabilities on First Workspace Admin

Bootstrapped via EP-00 workspace creation: first member receives all capabilities. Subsequent invites receive `[]` by default.

---

## 2. Configuration Entities

### Schema Overview

```
workspace_memberships
  ├── capabilities: text[]
  └── context_labels: text[]

projects
  ├── context_sources (1:many)
  ├── context_preset_id → context_presets
  ├── template_bindings (jsonb)
  └── team_ids: uuid[]

context_presets
  └── context_sources (1:many via preset_id)

validation_rules
  ├── workspace_id
  ├── project_id (nullable — null = workspace scope)
  ├── work_item_type
  ├── validation_type
  └── enforcement: required | recommended | blocked_override

routing_rules
  ├── workspace_id
  ├── project_id (nullable)
  ├── work_item_type (nullable — null = all types)
  ├── suggested_team_id
  ├── suggested_owner_context_label
  └── suggested_template_id

invitations
  ├── email
  ├── token_hash
  ├── expires_at
  ├── state: invited | accepted | cancelled
  ├── context_labels: text[]
  └── team_ids: uuid[]

audit_events  (append-only)
  ├── actor_id
  ├── actor_display
  ├── action
  ├── entity_type
  ├── entity_id
  ├── before_value: jsonb
  ├── after_value: jsonb
  └── context: jsonb

integration_configs
  ├── workspace_id
  ├── project_id (nullable)
  ├── provider          (jira | <future providers>)
  ├── base_url
  ├── auth_type
  ├── credentials_ref  (reference to secrets store, NOT plaintext)
  ├── state: active | disabled | error
  └── last_health_check_status

integration_project_mappings  (project-scoped per resolution #31)
  ├── id
  ├── integration_config_id
  ├── project_id            (workspace project)
  ├── jira_project_key
  └── work_item_type_mappings: jsonb

-- No jira_sync_logs table (resolution #26): polling + webhooks are removed; export is
-- user-initiated upsert-by-key (EP-11). Audit of exports lives in `audit_events`.
```

### Key Indexing Strategy

```sql
-- Capability checks on every request
CREATE INDEX idx_workspace_memberships_workspace_state ON workspace_memberships(workspace_id, state);

-- Rule resolution (hot path — every work_item creation)
CREATE INDEX idx_validation_rules_lookup ON validation_rules(workspace_id, project_id, work_item_type, active);
CREATE INDEX idx_routing_rules_lookup ON routing_rules(workspace_id, project_id, work_item_type, active);

-- Fixed per backend_review.md ALG-7: partial UNIQUE prevents silent duplicate-rule override.
-- RulePrecedenceService.resolve_validation_rules() builds ws_by_type as a dict keyed on
-- validation_type. If two active workspace rules exist for the same (workspace_id, work_item_type,
-- validation_type) and project_id IS NULL, the later rule silently overwrites the earlier one.
-- This constraint enforces uniqueness at DB level.
CREATE UNIQUE INDEX uq_validation_rules_workspace_scope
    ON validation_rules(workspace_id, work_item_type, validation_type)
    WHERE project_id IS NULL AND active = true;

-- Audit log queries — no partitioning (resolution #31). Scale is small enough that
-- the three composite indexes below are sufficient. Re-evaluate at >1M audit rows.
CREATE INDEX idx_audit_events_actor  ON audit_events(actor_id, created_at DESC);
CREATE INDEX idx_audit_events_entity ON audit_events(entity_type, entity_id, created_at DESC);
CREATE INDEX idx_audit_events_action ON audit_events(action, created_at DESC);

-- Orphan detection (support tools)
CREATE INDEX idx_work_items_owner_state ON work_items(workspace_id, owner_id, state) WHERE state NOT IN ('ready', 'archived', 'cancelled');
```

---

## 3. Rule Precedence Engine

Single service function, no strategy pattern needed:

```python
class RulePrecedenceService:
    async def resolve_validation_rules(
        self, workspace_id: UUID, project_id: UUID | None, work_item_type: WorkItemType
    ) -> list[ResolvedValidationRule]:
        workspace_rules = await self._rule_repo.get_active(workspace_id, None, work_item_type)
        project_rules = await self._rule_repo.get_active(workspace_id, project_id, work_item_type) if project_id else []

        # Index workspace rules by validation_type
        ws_by_type = {r.validation_type: r for r in workspace_rules}
        proj_by_type = {r.validation_type: r for r in project_rules}

        resolved = []
        all_types = set(ws_by_type) | set(proj_by_type)
        for vtype in all_types:
            ws_rule = ws_by_type.get(vtype)
            proj_rule = proj_by_type.get(vtype)

            if ws_rule and ws_rule.enforcement == Enforcement.BLOCKED_OVERRIDE:
                # Global blocker: workspace rule always wins
                resolved.append(ResolvedValidationRule(rule=ws_rule, source="workspace", supersedes=proj_rule))
            elif proj_rule:
                # Project rule overrides workspace rule
                resolved.append(ResolvedValidationRule(rule=proj_rule, source="project", supersedes=ws_rule))
            elif ws_rule:
                resolved.append(ResolvedValidationRule(rule=ws_rule, source="workspace", supersedes=None))

        return resolved
```

This is a pure function. No inheritance tree, no strategy factory. 30 lines.

---

## 4. Audit Events Schema

> **Schema ownership (per db_review.md SD-3)**: `audit_events` is defined in EP-00 with
> a `category` column (`auth | admin | domain`). EP-10 does NOT CREATE TABLE — it writes
> rows with `category='admin'` or `category='domain'`. Auth events continue to use the
> same table with `category='auth'`. Indexes and immutability RULEs are declared in EP-00.

### Write Path

Every mutation in admin services calls `AuditService.record(category='admin', ...)`. This is a direct DB insert within the same transaction as the mutation — not a Celery task, not a separate HTTP call. Audit is synchronous and atomic with the action.

```python
@dataclass
class AuditEventPayload:
    category: str                  # 'admin' | 'domain' (auth writes from EP-00 auth service)
    workspace_id: UUID
    actor_id: UUID | None
    actor_display: str
    action: str                    # snake_case verb, e.g. "member_suspended"
    entity_type: str               # snake_case noun, e.g. "workspace_member"
    entity_id: UUID
    before_value: dict | None = None
    after_value: dict | None = None
    context: dict | None = None    # extra metadata, e.g. {project_id, scope}
```

### Immutability Enforcement

Declared in EP-00 (single source of truth). EP-10 migration does NOT re-declare the RULEs.

### Read Path

`GET /api/v1/admin/audit-log` hits the table directly — no aggregation, no separate audit DB. Use the indexed queries. At current scale, this is fine. If audit grows to >10M rows, archive to cold storage (out of scope). ⚠️ originally MVP-scoped — see decisions_pending.md

> **Performance note (per backend_review.md TC-5)**: Synchronous `AuditService.record()` within the caller's transaction is the correct choice — async audit risks losing events on crash. The three indexes on `audit_events` (actor, entity, action) add ~3ms per write at 100k rows — acceptable at current scale. At >1M audit rows, consider partitioning `audit_events` by month to keep index size manageable. No change needed currently. ⚠️ originally MVP-scoped — see decisions_pending.md

---

## 5. Health Dashboard: Aggregation Queries

No materialized views — run queries on-demand with a Redis cache (TTL 60 seconds, resolution #25/#31).

> **LV-4 fix (per backend_review.md LV-4)**: SQL aggregations must NOT live in `HealthDashboardService`. Each aggregation is a method on `DashboardRepository` in the infrastructure layer. `DashboardService` calls these methods and assembles the response. This makes aggregation queries testable in isolation.

```python
# domain/repositories/dashboard_repository.py (interface)
class IDashboardRepository(Protocol):
    async def get_workspace_health(self, workspace_id: UUID, project_id: UUID | None) -> WorkspaceHealthData: ...
    async def get_org_health(self, workspace_id: UUID) -> OrgHealthData: ...
    async def get_process_health(self, workspace_id: UUID, project_id: UUID | None) -> ProcessHealthData: ...
    async def get_integration_health(self, workspace_id: UUID) -> IntegrationHealthData: ...

# application/services/dashboard_service.py
class HealthDashboardService:
    def __init__(self, repo: IDashboardRepository, cache: DashboardCache): ...
    # Calls repo methods, assembles result, handles cache TTL
    # NO direct SQL here

# infrastructure/persistence/sqlalchemy/dashboard_repo_impl.py
# SQL aggregations live here:
#   get_workspace_health: SELECT state, COUNT(*) FROM work_items WHERE workspace_id=? GROUP BY state
#   get_org_health: teamless_members LEFT JOIN, top_loaded_owners GROUP BY owner_id
#   get_process_health: override_rate, most_skipped_validations
#   get_integration_health: integration_configs (provider='jira') + jira_sync_logs aggregation
```

Cache key: `dashboard:{workspace_id}:{project_id or "global"}` — invalidated on any write to the relevant entities.

---

## 6. Jira Integration Config Model

### Credentials: Never in the DB Plaintext

```python
class CredentialsStore:
    """Thin wrapper around environment-configured secrets backend."""
    # Current: encrypted column in integration_configs using Fernet (symmetric, workspace-keyed)
    # Future: HashiCorp Vault / AWS Secrets Manager swap in here
    # (originally MVP-scoped — see decisions_pending.md)
    
    def store(self, config_id: UUID, credentials: dict) -> str:
        """Returns opaque reference key."""
        ...

    def retrieve(self, ref: str) -> dict:
        """Returns decrypted credentials. Never called on GET endpoints."""
        ...

    def rotate(self, old_ref: str, new_credentials: dict) -> str:
        """Atomic rotate: write new, delete old."""
        ...
```

`integration_config.credentials_ref` stores the opaque reference string. The actual credentials are encrypted at rest in a separate table or external store, never in `integration_configs`.

### Health Check Task (Celery)

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def check_jira_health(self, config_id: str):
    config = JiraConfigRepository.get(config_id)
    credentials = CredentialsStore.retrieve(config.credentials_ref)
    result = JiraClient.probe(config.base_url, credentials)
    JiraConfigRepository.update_health(config_id, result)
    if result.status != "ok":
        if config.consecutive_failures >= 3:
            NotificationService.dispatch_jira_degraded(config_id)
```

---

## 7. Admin API Endpoint Grouping

```
/api/v1/admin/
  members/
    GET, POST invite
    {id}/  PATCH (state, capabilities, context-labels)
    invitations/{id}/resend  POST

  rules/
    validation/  GET, POST, PATCH {id}, DELETE {id}
    routing/     GET, POST, PATCH {id}, DELETE {id}

  projects/
    GET, POST
    {id}/  GET, PATCH
    {id}/context-sources/  GET, POST, PUT
    {id}/context-sources/{source_id}  DELETE
    {id}/template-bindings  PATCH

  context-presets/
    GET, POST
    {id}/  GET, PATCH, DELETE

  integrations/
    jira/  GET, POST
    jira/{id}/  GET, PATCH
    jira/{id}/test  POST
    jira/{id}/mappings/  GET, POST
    jira/{id}/sync-logs/  GET
    jira/sync-logs/{log_id}/retry  POST

  audit-log/  GET

  dashboard/  GET

  support/
    orphaned-work-items/  GET
    reassign-owner/  POST
    pending-invitations/  GET
    failed-exports/  GET
    failed-exports/retry-all  POST
    config-blocked-work-items/  GET
```

All routes under `/api/v1/admin/` require authenticated member with at least one admin capability (base check before specific capability checks). This prevents information disclosure to plain members.

---

## 8. Admin Middleware Stack

```
Request
  └── JWTAuthMiddleware (EP-00)         → populates request.user
  └── WorkspaceMemberMiddleware          → loads workspace_member, checks state (active only)
  └── AdminBaseMiddleware                → rejects if member has zero capabilities
  └── Endpoint-specific dependency       → require_capabilities(Capability.XYZ)
  └── Handler
```

The `WorkspaceMemberMiddleware` is shared with EP-08. The `AdminBaseMiddleware` is new to EP-10.

---

## 9. Layer Breakdown (DDD)

```
domain/
  models/
    workspace_member.py      (Member, MemberState, Capability, ContextLabel)
    validation_rule.py       (ValidationRule, Enforcement, WorkItemType)
    routing_rule.py          (RoutingRule)
    project.py               (Project, ProjectState, ContextSource, ContextPreset)
    jira_config.py           (JiraConfig, JiraProjectMapping, JiraSyncLog)
    audit_event.py           (AuditEvent — immutable value object)
  repositories/
    workspace_member_repo.py
    rule_repo.py
    project_repo.py
    jira_config_repo.py
    audit_repo.py            (write-only interface — no update/delete methods)

application/
  services/
    member_service.py        (invite, activate, suspend, delete, grant_capabilities)
    rule_service.py          (CRUD + precedence resolution)
    project_service.py       (CRUD + context source management + preset management)
    jira_config_service.py   (CRUD + credentials + mapping)
    audit_service.py         (record — synchronous write within caller's transaction)
    dashboard_service.py     (aggregation queries + cache)
    support_service.py       (orphan detection, reassign, bulk retry)

presentation/
  controllers/
    members_controller.py
    rules_controller.py
    projects_controller.py
    integration_controller.py
    audit_controller.py
    dashboard_controller.py
    support_controller.py
  dependencies/
    auth.py                  (require_capabilities)

infrastructure/
  persistence/
    sqlalchemy/
      member_repo_impl.py
      rule_repo_impl.py
      project_repo_impl.py
      jira_repo_impl.py
      audit_repo_impl.py
  adapters/
    jira/
      jira_client.py         (thin HTTP wrapper, probe, export)
      credentials_store.py   (encrypt/decrypt, store/retrieve/rotate)
  tasks/
    jira_health_check.py
    jira_export.py
    notification_fanout.py   (reuse EP-08 pattern)
```

---

## 10. Decisions and Tradeoffs

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Permission model | Capability array on member | RBAC tables | Current scope doesn't need role inheritance; array is simpler, direct, testable ⚠️ originally MVP-scoped — see decisions_pending.md |
| Credential storage | Fernet-encrypted column with documented key rotation | External vault | No external vault (resolution #31). Fernet symmetric key from env var + rotation runbook is sufficient at scale. |
| Audit write | Synchronous within transaction | Async event | Audit MUST be consistent with the action; async risks losing events on crash |
| Rule precedence | Pure function, explicit logic | Strategy pattern | No polymorphism needed; 30 lines of explicit logic beats a class hierarchy |
| Dashboard data | On-demand queries + Redis cache (60s TTL) | Materialized views | No MV (resolution #25). Data volume is small; on-demand + short cache is enough. |
| Health check | Celery periodic task | Cron / APScheduler | Already have Celery for EP-08; consistent infrastructure |

---

## 11. Superadmin Powers

Superadmin is a global flag (`users.is_superadmin`) — NOT a workspace capability. It exists outside workspace scope by design.

**Bootstrap (resolution #31)**: `SEED_SUPERADMIN_EMAILS` env var or migration fixture. No CLI. First Google OAuth login of a seeded email creates the `users` row with `is_superadmin = true`. Subsequent grants flow through the audited endpoint below.

### Superadmin surface (in-scope per resolution #31)

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/admin/workspaces` | Create workspace + assign initial Workspace Admin. |
| GET | `/api/v1/admin/workspaces` | List all workspaces across the platform. |
| GET | `/api/v1/admin/users` | List all users across the platform. |
| GET | `/api/v1/admin/audit?scope=global` | Query `audit_events` across all workspaces (no `workspace_id` filter applied). |
| GET | `/api/v1/admin/health/global` | Platform-wide health snapshot. |
| POST | `/api/v1/admin/users/:id/grant-superadmin` | Elevate a user to superadmin (audited). |

UI: admin sections are rendered only when `user.is_superadmin === true`.

### Deferred (explicitly out of scope for now)

- Suspend an entire workspace
- Force-unlock a section on behalf of a workspace (delegated to Workspace Admin)
- Impersonate another user
- Bulk CSV import/export
- Cross-workspace owner reassignment

Re-introducing any of these requires a new decision recorded in `decisions_pending.md`.

**Capability `force_unlock`** is granted to Workspace Admin (via profile) and automatically to superadmin (via short-circuit).

---

## 12. Tag Admin Integration (EP-15)

Tag CRUD is implemented in EP-15. This epic owns the admin layout entry point and capability enforcement.

- Admin left-nav entry: **Tags** → `/admin/tags` (route implemented in EP-15)
- Capability `manage_tags`: CRUD operations on workspace tags — create, rename, archive
- Capability `merge_tags`: merge one tag into another (higher bar — workspace admins only; destructive, can't be undone)
- Audit events for all tag operations: `tag_created`, `tag_renamed`, `tag_archived`, `tag_merged` — follow `AuditEventPayload` pattern with `category='admin'`, `entity_type='tag'`
- EP-10 adds capability enforcement wrappers and audit hooks around EP-15's tag service calls

---

## 13. Puppet Integration

Reuses `integration_configs` table with `provider='puppet'`.

**Config fields** (stored in `integration_configs`):

| Field | Detail |
|-------|--------|
| `api_endpoint` | Puppet API base URL (must be HTTPS) |
| `api_key` | Fernet-encrypted (same `CredentialsStore` as Jira) |
| `default_index_name` | Default Puppet knowledge base index |
| `documentation_sources` | `text[]` — list of external URLs/paths to index |

**Admin capability**: `manage_puppet_integration` (workspace admin).

**Health check**: delegates to EP-13's `PuppetAdapter.probe()`. Returns `{ status: ok|auth_failure|unreachable, last_sync_at }`.

**API surface** (admin endpoints, owned by this epic):

```
/api/v1/admin/integrations/puppet/   GET, POST
/api/v1/admin/integrations/puppet/{id}/  GET, PATCH
/api/v1/admin/integrations/puppet/{id}/test  POST
/api/v1/admin/integrations/puppet/{id}/sources/  GET, POST, DELETE {source_id}
```

**Credentials policy**: same as Jira — never returned in any GET response, never logged, Fernet-encrypted at rest.

---

## 14. Out of Scope

> ⚠️ Items below were originally MVP-scoped deferrals. Review each against full-product scope; log outcomes in decisions_pending.md.

- Multi-workspace capability delegation chains
- Role templates (predefined capability bundles — users assemble manually)
- Audit log archiving / cold storage rotation
- Webhook notifications for admin events
- Project-specific Jira credentials (project_id scoped integration_config supported by schema, but UI/API is workspace-only)
- Bulk member import via CSV
