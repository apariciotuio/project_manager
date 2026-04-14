# EP-10 Backend Subtasks — Configuration, Projects, Rules & Administration

**Stack**: Python 3.12 / FastAPI / SQLAlchemy async / PostgreSQL 16 / Redis / Celery
**Depends on**: EP-12 middleware stack (correlation ID, auth, rate limit), EP-00 (JWT), EP-08 (SSE notifications)

---

## API Contract (interface for frontend)

### Members & Invitations
```
GET    /api/v1/admin/members               ?state=&teamless=bool&cursor=&limit=
                                           Response: { data: [Member], pagination }
POST   /api/v1/admin/members               Body: { email, context_labels[], team_ids[] }
                                           Response 201: { member_id, invitation_id }
PATCH  /api/v1/admin/members/{id}          Body: { state?, capabilities?, context_labels? }
                                           Response 200: Member
POST   /api/v1/admin/members/invitations/{id}/resend
                                           Response 202
Member: { id, email, display_name, state, capabilities[], context_labels[], team_ids[], created_at }
Capability enum: invite_members | deactivate_members | manage_teams |
                 configure_workspace_rules | configure_project | configure_integration |
                 view_audit_log | view_admin_dashboard | reassign_owner | retry_exports |
                 force_unlock | manage_tags | merge_tags | manage_puppet_integration
Errors: 403 (missing capability), 409 (duplicate active email), 422 (validation)
```

### Validation & Routing Rules
```
GET    /api/v1/admin/rules/validation      ?workspace_id=&project_id=&type=
                                           Response: { data: [Rule with effective/superseded_by] }
POST   /api/v1/admin/rules/validation      Body: { project_id?, work_item_type, validation_type, enforcement }
PATCH  /api/v1/admin/rules/validation/{id} Body: { enforcement?, active? }
DELETE /api/v1/admin/rules/validation/{id}
                                           Response 204 / 409 (has history)
GET    /api/v1/admin/rules/routing         ?workspace_id=&project_id=&type=
POST   /api/v1/admin/rules/routing         Body: { project_id?, work_item_type?, suggested_team_id?,
                                                    suggested_owner_context_label?, suggested_template_id? }
PATCH  /api/v1/admin/rules/routing/{id}
DELETE /api/v1/admin/rules/routing/{id}
Rule: { id, workspace_id, project_id?, work_item_type, validation_type, enforcement,
        active, effective, superseded_by? }
Enforcement enum: required | recommended | blocked_override
```

### Projects & Context
```
GET    /api/v1/admin/projects              Response: { data: [Project] }
POST   /api/v1/admin/projects              Body: { name, description?, team_ids[], context_preset_id? }
GET    /api/v1/admin/projects/{id}
PATCH  /api/v1/admin/projects/{id}         Body: { name?, description?, state?, team_ids?,
                                                    context_preset_id?, template_bindings? }
GET    /api/v1/admin/projects/{id}/context-sources
POST   /api/v1/admin/projects/{id}/context-sources
PUT    /api/v1/admin/projects/{id}/context-sources    (bulk replace)
DELETE /api/v1/admin/projects/{id}/context-sources/{source_id}
PATCH  /api/v1/admin/projects/{id}/template-bindings  Body: { bindings: jsonb }
GET    /api/v1/admin/context-presets
POST   /api/v1/admin/context-presets
GET    /api/v1/admin/context-presets/{id}
PATCH  /api/v1/admin/context-presets/{id}
DELETE /api/v1/admin/context-presets/{id}  Response 204 / 409 (in use)
Project: { id, name, state, team_ids[], context_preset_id?, template_bindings, created_at }
```

### Jira Integration
```
GET    /api/v1/admin/integrations/jira
POST   /api/v1/admin/integrations/jira     Body: { base_url, auth_type, credentials: {token, email} }
                                           Response 201: { id, state } — credentials NOT returned
GET    /api/v1/admin/integrations/jira/{id}
PATCH  /api/v1/admin/integrations/jira/{id} Body: { credentials? (re-encrypt), state? }
POST   /api/v1/admin/integrations/jira/{id}/test
                                           Response 200: { status: ok|auth_failure|unreachable }
GET    /api/v1/admin/integrations/jira/{id}/mappings
POST   /api/v1/admin/integrations/jira/{id}/mappings
GET    /api/v1/admin/integrations/jira/{id}/sync-logs  ?status=&cursor=&limit=
POST   /api/v1/admin/integrations/jira/sync-logs/{id}/retry
JiraConfig: { id, base_url, auth_type, state, last_health_check_status, created_at }
NEVER return credentials in any response.
```

### Puppet Integration
```
GET    /api/v1/admin/integrations/puppet
POST   /api/v1/admin/integrations/puppet
    Body: { api_endpoint, api_key, default_index_name, documentation_sources[] }
    Response 201: { id, state } — api_key NOT returned
GET    /api/v1/admin/integrations/puppet/{id}
PATCH  /api/v1/admin/integrations/puppet/{id}
    Body: { api_key? (re-encrypt), default_index_name?, documentation_sources? }
POST   /api/v1/admin/integrations/puppet/{id}/test
    Response 200: { status: ok|auth_failure|unreachable, last_sync_at }
GET    /api/v1/admin/integrations/puppet/{id}/sources
POST   /api/v1/admin/integrations/puppet/{id}/sources
DELETE /api/v1/admin/integrations/puppet/{id}/sources/{source_id}
PuppetConfig: { id, api_endpoint, default_index_name, documentation_sources[], state, last_health_check_status, last_health_check_at }
NEVER return api_key in any response.
Capability: manage_puppet_integration
Note: endpoints delegate to EP-13's PuppetAdapter and PuppetConfigService; this epic owns the admin endpoint surface only.
```

### Audit Log
```
GET    /api/v1/admin/audit-log
    ?actor_id=&action=&entity_type=&entity_id=&from=&to=&cursor=&limit=200 (max)
Response: { data: [AuditEvent], pagination }
AuditEvent: { id, actor_id, actor_display, action, entity_type, entity_id,
              before_value, after_value, context, created_at }
```

### Admin Dashboard (Health)
```
GET    /api/v1/admin/dashboard  ?project_id=
Response: {
  workspace_health: { states: [{state, count}], critical_blocks, avg_time_to_ready, stale_reviews },
  org_health: { active_members, teamless_members, teams_without_lead, top_loaded_owners[] },
  process_health: { override_rate, most_skipped_validations[], exported_count, blocked_by_type[] },
  integration_health: { jira_configs: [{id, state, error_streak, export_counts}] }
}
```

### Superadmin Operations
```
POST   /api/v1/admin/users
    Body: { email, display_name, workspace_id, initial_capabilities[] }
    Response 201: { id, email, display_name }
    Auth: require_superadmin (403 for non-superadmin)
    Note: creates user directly, bypassing OAuth invitation — for bootstrap before Google OAuth is configured

GET    /api/v1/admin/audit/cross-workspace
    ?actor_id=&action=&entity_type=&from=&to=&cursor=&limit=200 (max)
    Response: { data: [AuditEvent], pagination }
    Auth: require_superadmin — queries audit_events with NO workspace_id filter
    Note: workspace-scoped audit log remains at GET /api/v1/admin/audit-log

CLI: python -m app.cli create-superadmin --email=<email>
    Sets is_superadmin=True on existing user (or creates user if not found).
    No HTTP endpoint. Run on server or via deployment pipeline for first-time bootstrap.
```

### Support Tools
```
GET    /api/v1/admin/support/orphaned-work-items
GET    /api/v1/admin/support/pending-invitations    ?expiring_soon=bool
GET    /api/v1/admin/support/failed-exports
GET    /api/v1/admin/support/config-blocked-work-items
POST   /api/v1/admin/support/reassign-owner         Body: { work_item_id, new_owner_id }
POST   /api/v1/admin/support/failed-exports/retry-all
                                                    Response 202 / 429 (10 min rate limit)
```

---

## Group 0 — Migrations & Schema

- [ ] Migration: add `capabilities text[]` and `context_labels text[]` to `workspace_memberships`
- [ ] Migration: add GIN index on `workspace_memberships(capabilities)`
- [ ] Migration: create `invitations` table (email, token_hash, expires_at, state, context_labels, team_ids, created_by)
- [ ] Migration: create `validation_rules` table with all fields + GIN/btree indexes
- [ ] Migration: add partial UNIQUE index `uq_validation_rules_workspace_scope ON validation_rules(workspace_id, work_item_type, validation_type) WHERE project_id IS NULL AND active = true` — prevents silent duplicate workspace-scope rule override in RulePrecedenceService (Fixed per backend_review.md ALG-7)
- [ ] Migration: create `routing_rules` table with all fields + indexes
- [ ] Migration: create `projects` table (name, description, state, team_ids, context_preset_id, template_bindings jsonb)
- [ ] Migration: create `context_sources` table (project_id nullable, preset_id nullable, type, label, url, description, active)
- [ ] Migration: create `context_presets` table (workspace_id, name, description)
- [ ] Migration: create `jira_configs` table (workspace_id, project_id nullable, base_url, auth_type, credentials_ref, state, health fields)
- [ ] Migration: create `jira_project_mappings` table
- [ ] `audit_events` table + PG RULEs are created by EP-00 (shared unified table — see EP-00 design.md §audit_events). EP-10 writes only with `category IN ('admin','domain')`. Do NOT redeclare the table or the rules here.
- [ ] Add composite indexes per design.md section 2 (workspace_state, validation_rules_lookup, routing_rules_lookup, audit indexes, work_items_owner_state). No `sync_log_status` — decision #26 removed `sync_logs`.
- [ ] Verify all foreign keys, NOT NULL constraints, enum constraints

---

## Group 1 — Domain Models

- [ ] `domain/models/workspace_member.py` — `Capability` enum (10 values), `MemberState` enum, `ContextLabel`, update `WorkspaceMember` entity
- [ ] `domain/models/invitation.py` — `Invitation` entity, `InvitationState` enum
- [ ] `domain/models/validation_rule.py` — `ValidationRule`, `Enforcement` (required|recommended|blocked_override), `ElementType`
- [ ] `domain/models/routing_rule.py` — `RoutingRule`
- [ ] `domain/models/project.py` — `Project`, `ProjectState`, `ContextSource`, `ContextPreset`, `TemplateBinding`
- [ ] `domain/models/jira_config.py` — `JiraConfig`, `JiraProjectMapping`, `JiraHealthStatus` (no `JiraSyncLog` — decision #26 removed sync logs)
- [ ] `domain/models/audit_event.py` — `AuditEvent` as immutable frozen dataclass; no setters

---

## Group 2 — Repository Interfaces

- [ ] `domain/repositories/workspace_member_repo.py` — get_by_id, get_by_workspace, get_teamless, update_capabilities, update_state
- [ ] `domain/repositories/invitation_repo.py` — create, get_by_token_hash, get_by_email, update_state
- [ ] `domain/repositories/rule_repo.py` — CRUD for validation + routing rules; `get_active(workspace_id, project_id, element_type)`
- [ ] `domain/repositories/project_repo.py` — project, context_source, context_preset CRUD
- [ ] `domain/repositories/jira_repo.py` — jira_config and mappings CRUD
- [ ] `domain/repositories/audit_repo.py` — write-only: `record(payload)` only; no update/delete methods on interface
- [ ] `domain/repositories/dashboard_repo.py` — `IDashboardRepository` interface: `get_workspace_health`, `get_org_health`, `get_process_health`, `get_integration_health` (Fixed per backend_review.md LV-4 — SQL aggregations belong in infrastructure, not in DashboardService)

---

## Group 3 — Infrastructure Layer

- [ ] `infrastructure/adapters/jira/credentials_store.py` — Fernet encrypt/decrypt, store/retrieve/rotate; never returns plaintext to callers
- [ ] `infrastructure/adapters/jira/jira_client.py` — HTTP wrapper: `probe()`, `export_element()`, `get_project()`; raises typed errors only
- [ ] `presentation/dependencies/auth.py` — `require_capabilities(*caps)` FastAPI dependency (testable, not a decorator)
- [ ] `presentation/middleware/admin_base.py` — AdminBaseMiddleware: reject with 403 if member has zero capabilities
- [ ] SQLAlchemy repo implementations: `member_repo_impl.py`, `rule_repo_impl.py`, `project_repo_impl.py`, `jira_repo_impl.py`, `audit_repo_impl.py`

---

## Group 4 — Phase 1: Members & Capabilities (US-105, US-106)

### Acceptance Criteria

WHEN `POST /api/v1/admin/members` is called by a member with `invite_members` capability for a new email
THEN the response is 201 with `{member_id, invitation_id}`
AND an invitation email is dispatched via Celery background task
AND `audit_events` contains an entry with `action: member_invited`, `entity: invitation`, email present (no token value)

WHEN `POST /api/v1/admin/members` is called for an already-active email
THEN the API returns HTTP 409 with `error.code: member_already_active`

WHEN `POST /api/v1/admin/members` is called for a pending-invited email
THEN the API returns HTTP 409 with `error.code: invite_pending` and `{invitation_id, resend_url}` in the response

WHEN a member without `invite_members` capability calls `POST /api/v1/admin/members`
THEN the API returns HTTP 403 with `error.code: capability_required` — the handler is never reached

WHEN `PATCH /api/v1/admin/members/{id}` sets `state: suspended` for the last workspace admin
THEN the API returns HTTP 409 with `error.code: cannot_suspend_last_admin`

WHEN a suspended member sends any write request
THEN the API returns HTTP 403 with `error.code: member_suspended` regardless of endpoint

WHEN `PATCH /api/v1/admin/members/{id}/capabilities` grants a capability the acting member does not hold
THEN the API returns HTTP 403 with `error.code: cannot_grant_unpossessed_capability`

WHEN `PATCH /api/v1/admin/members/{id}/context-labels` is called with a label outside the allowed set
THEN the API returns HTTP 422

WHEN `POST /api/v1/admin/members/invitations/{id}/resend` is called for an invitation not in `invited` state
THEN the API returns HTTP 409 with `error.code: invite_not_resendable`

WHEN `GET /api/v1/admin/members?teamless=true` is called
THEN only members with no team membership are returned

## Group 4 — Phase 1: Members & Capabilities (US-105, US-106)

- [ ] [RED] `test_member_service_invite` — success, duplicate active email (409), duplicate invited email (resend path)
- [ ] [RED] `test_member_service_activation` — via token, expired token, no invite for email
- [ ] [RED] `test_member_service_suspend` — success, last-admin guard, orphan-owner alert queued
- [ ] [RED] `test_member_service_delete` — success, last-admin guard, session invalidation called
- [ ] [RED] `test_member_service_reactivate` — from suspended succeeds, from deleted rejected
- [ ] [RED] `test_grant_capabilities` — success, grant unpossessed (rejected), unknown capability (rejected)
- [ ] [RED] `test_context_labels` — set, empty, invalid label
- [ ] [RED] `test_require_capabilities_dependency` — active+cap passes, missing cap=403, suspended=403
- [ ] [RED] `test_invite_resend` — success, non-resendable state, new token replaces old
- [ ] [RED] `test_member_listing_filters` — by state, teamless, pagination
- [ ] [GREEN] `application/services/member_service.py` — invite, activate, suspend, delete, reactivate, grant_capabilities, set_context_labels
- [ ] [GREEN] Celery task: send invitation email — MUST be dispatched AFTER the DB transaction commits; use `after_commit` hook or equivalent; dispatching inside the open transaction risks sending an email that refers to an invitation that gets rolled back (Fixed per backend_review.md SD-5)
- [ ] [RED] Test `MemberService.invite()` Celery task dispatch ordering: task is NOT enqueued if DB transaction rolls back
- [ ] [GREEN] Audit: all member mutations call `AuditService.record()` within same transaction
- [ ] [REFACTOR] Extract orphan-owner alert to shared `AlertService`

---

## Group 5 — Phase 2: Validation Rules & Routing (US-102, US-103)

### Acceptance Criteria

WHEN `resolve_validation_rules(workspace_id, project_id, element_type)` is called
THEN project-level rules take precedence over workspace-level rules for the same `(element_type, validation_type)` combination
AND workspace-level rules with `enforcement=blocked_override` always apply regardless of project rules
AND when no rules match, an empty list is returned (no error)

WHEN `POST /api/v1/admin/rules/validation` is called with a `project_id` and a workspace-level `blocked_override` rule exists for the same `(element_type, validation_type)`
THEN the API returns HTTP 409 with `error.code: global_blocker_in_effect`

WHEN `POST /api/v1/admin/rules/validation` is called and a rule already exists for the same `(workspace_id, project_id, element_type, validation_type)`
THEN the API returns HTTP 409 with `error.code: rule_already_exists` and the existing rule ID in the response

WHEN `PATCH /api/v1/admin/rules/validation/{id}` changes enforcement to `blocked_override`
THEN existing project-level rules for the same `(element_type, validation_type)` are flagged as `superseded: true`
AND a `warnings` array is returned in the response listing the superseded rule IDs

WHEN `DELETE /api/v1/admin/rules/validation/{id}` is called for a rule with historical references
THEN the API returns HTTP 409 with `error.code: rule_has_history`

WHEN `GET /api/v1/admin/rules/validation?project_id=X` is called
THEN both workspace-level and project-level rules are returned
AND each rule includes `effective: bool` and `superseded_by: rule_id | null`

WHEN `POST /api/v1/admin/rules/routing` is submitted with all suggestion fields null
THEN the API returns HTTP 422 with `error.code: routing_rule_empty`

WHEN `suggested_team_id` references a non-existent team
THEN the API returns HTTP 422 with `error.code: team_not_found`

WHEN suspended members exist and routing suggestions are resolved
THEN those members are excluded from `suggested_validators` results

## Group 5 — Phase 2: Validation Rules & Routing (US-102, US-103)

- [ ] [RED] `test_rule_precedence_engine` — project overrides workspace, blocked_override always wins, no project rule falls back, no rules returns empty
- [ ] [RED] `test_validation_rule_service_create` — workspace scope, project scope, duplicate rejected, blocked_override rejects conflicting project rule
- [ ] [RED] `test_validation_rule_service_update` — partial update, enforcement change to blocked_override flags superseded project rules
- [ ] [RED] `test_validation_rule_delete` — no history: deletes; has history: 409
- [ ] [RED] `test_routing_rule_create` — empty rule rejected, invalid team rejected
- [ ] [RED] `test_routing_suggestions` — project-first precedence, null when no rules, suspended members excluded
- [ ] [RED] `test_rule_list_with_precedence_annotation` — correct `effective`, `superseded_by` fields
- [ ] [GREEN] `application/services/rule_service.py` — CRUD for validation + routing rules
- [ ] [GREEN] `application/services/rule_precedence_service.py` — pure `resolve_validation_rules()` and `resolve_routing_suggestion()` (30 lines, no strategy pattern)
- [ ] [GREEN] Audit: all rule mutations call `AuditService.record()`
- [ ] [REFACTOR] Confirm rule resolution used by element creation endpoint (EP-08 integration point)

---

## Group 6 — Phase 3: Projects & Context (US-100, US-101)

- [ ] [RED] `test_project_service_create` — success, duplicate name rejected, invalid team IDs rejected
- [ ] [RED] `test_project_context_sources` — add, remove (no retroactive purge), bulk replace
- [ ] [RED] `test_project_archive` — success, open-elements alert, element creation blocked in archived project
- [ ] [RED] `test_context_preset_create` — success, duplicate name rejected
- [ ] [RED] `test_context_preset_update` — sources updated, linked projects affected, warning returned
- [ ] [RED] `test_context_preset_delete` — not in use: deletes; in use: 409
- [ ] [RED] `test_project_preset_link` — success, inline sources preserved, invalid preset rejected
- [ ] [RED] `test_template_binding` — binding created, default not mandatory
- [ ] [RED] `test_project_team_deletion_cascade` — team deleted → project team_ids cleaned, alert queued
- [ ] [GREEN] `application/services/project_service.py` — project CRUD, context source CRUD, preset CRUD, template bindings
- [ ] [GREEN] Audit: all project/preset/source mutations call `AuditService.record()`
- [ ] [REFACTOR] Confirm context sources used by enrichment service (AI layer integration point)

---

## Group 7 — Phase 4: Jira Integration (US-104)

### Acceptance Criteria

WHEN `POST /api/v1/admin/integrations/jira` is called with valid data
THEN the API returns 201 with `{id, state: "active"}` — the credentials_ref is NOT in the response
AND the audit log records `action: jira_config_created` with `config_id` only (no token values)
AND a Celery health check task is enqueued

WHEN `POST /api/v1/admin/integrations/jira` is called with `base_url` as an HTTP (non-HTTPS) URL
THEN the API returns HTTP 422 with `error.code: invalid_base_url`

WHEN a duplicate config exists for the same `(workspace_id, project_id=null)`
THEN the API returns HTTP 409 with `error.code: jira_config_exists`

WHEN `POST /api/v1/admin/integrations/jira/{id}/test` is called
THEN the API always returns HTTP 200 (connection test result is in the body: `status: ok|auth_failure|unreachable`)
AND `last_health_check_at` and `last_health_check_status` are updated on the jira_config record

WHEN `POST /api/v1/admin/integrations/jira/{id}/test` is called on a disabled config
THEN the API returns HTTP 409 with `error.code: config_disabled`

WHEN the health check Celery task records 3 consecutive failures
THEN `jira_config.state` transitions to `error`
AND an SSE notification is dispatched to all members with `configure_integration` or `view_admin_dashboard` capability

WHEN the health check task records success after an `error` state
THEN `jira_config.state` transitions back to `active`
AND `audit_events` records `action: jira_config_recovered`

WHEN `GET /api/v1/admin/integrations/jira/{id}` is called
THEN the response body contains NO `credentials_ref`, token, or auth field

WHEN `POST /api/v1/admin/integrations/jira/sync-logs/{id}/retry` is called for a `success` log
THEN the API returns HTTP 409 with `error.code: already_synced`

WHEN `POST /api/v1/admin/integrations/jira/sync-logs/{id}/retry` is called while config is in `disabled` or `error` state
THEN the API returns HTTP 409 with `error.code: integration_unavailable`

## Group 7 — Phase 4: Jira Integration (US-104)

- [ ] [RED] `test_jira_config_create` — success, credentials encrypted (assert not plaintext in DB), duplicate config rejected, invalid URL rejected
- [ ] [RED] `test_jira_config_update_credentials` — new credentials replace old, re-encryption, re-health-check queued
- [ ] [RED] `test_jira_connection_test` — ok, auth failure, unreachable; always returns HTTP 200
- [ ] [RED] `test_jira_health_check_task` — ok stays active, 3 consecutive failures → error state + SSE alert
- [ ] [RED] `test_jira_health_recovery` — error → ok → active, audit event recorded
- [ ] [RED] `test_jira_project_mapping` — success, jira project key validated, default type mappings applied
- [ ] [RED] `test_jira_credentials_never_in_response` — GET config returns no credential fields
- [ ] [RED] `test_jira_credentials_not_in_audit` — audit event for credential update has no token values
- [ ] [GREEN] `application/services/jira_config_service.py` — CRUD, test connection, disable/enable, mapping CRUD
- [ ] [GREEN] `infrastructure/tasks/jira_health_check.py` — Celery periodic task (max_retries=3, retry_delay=60)
- [ ] [GREEN] Audit: all Jira mutations call `AuditService.record()` (no credentials in payload)

---

## Group 8 — Phase 5: Audit Log (US-107)

### Acceptance Criteria

WHEN `AuditService.record(payload)` is called within a database transaction
THEN the `audit_events` row is inserted in the same transaction — if the transaction rolls back, the audit entry also rolls back

WHEN `AuditService.record()` is called
THEN `actor_display` is populated from the member record at write time
AND if the member is later deleted, the stored `actor_display` remains unchanged

WHEN any code calls `audit_repo.update()` or `audit_repo.delete()`
THEN those methods do not exist on the interface; the caller gets a compile/type error

WHEN the PostgreSQL `no_update_audit` and `no_delete_audit` rules are active
THEN an attempted UPDATE or DELETE on `audit_events` is silently rejected (no error propagated)
AND the row count returned is 0

WHEN `GET /api/v1/admin/audit-log` is called with `limit=201`
THEN the API caps at 200 and returns the response without error

WHEN `GET /api/v1/admin/audit-log` is called by a member lacking `view_audit_log` capability
THEN the API returns HTTP 403

## Group 8 — Phase 5: Audit Log (US-107)

- [ ] [RED] `test_audit_service_record` — inserts within caller transaction, all fields populated
- [ ] [RED] `test_audit_immutability` — no update method on repo interface; no delete method
- [ ] [RED] `test_audit_actor_display_preserved` — actor_display populated at write time from member record
- [ ] [RED] `test_audit_query_filters` — by actor_id, action, entity_type, entity_id, date range, combined
- [ ] [RED] `test_audit_pagination` — page_size respected, max 200 enforced
- [ ] [RED] `test_audit_deleted_member_display` — actor_display still present for deleted members
- [ ] [GREEN] `application/services/audit_service.py` — `record(payload)` only; synchronous; no read methods
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/audit_repo_impl.py` — insert only + filtered query
- [ ] [REFACTOR] Verify every mutation service calls AuditService; integration test: invite→activate→suspend audit trail

---

## Group 9 — Phase 6: Admin Health Dashboard (US-108)

- [ ] [RED] `test_workspace_health` — elements by state, critical blocks (>5 days), avg time to ready, stale reviews
- [ ] [RED] `test_org_health` — active count, teamless members, teams without lead, top loaded owners
- [ ] [RED] `test_process_health` — override rate, most skipped validations, exported vs not, blocked by type/team
- [ ] [RED] `test_integration_health` — ok, error, not configured, export counts
- [ ] [RED] `test_dashboard_empty_workspace` — all zeros, no errors
- [ ] [RED] `test_dashboard_project_scoped` — metrics scoped to project_id
- [ ] [RED] `test_dashboard_cache` — second call within TTL hits cache; invalidated on relevant write
- [ ] [GREEN] `application/services/dashboard_service.py` — orchestrates `IDashboardRepository` calls + Redis cache (TTL 5 min, key `dashboard:{workspace_id}:{project_id|global}`); NO SQL in service layer (Fixed per backend_review.md LV-4)
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/dashboard_repo_impl.py` — SQL aggregations live here; use SQLAlchemy core (not ORM) for aggregations
- [ ] [GREEN] Cache invalidation hooks: wire into member_service, rule_service, project_service, jira_config_service
- [ ] [REFACTOR] Profile each aggregation under 100+ elements, 20+ members; add EXPLAIN output to dev notes

---

## Group 10 — Phase 7: Support Tools (US-109)

### Acceptance Criteria

WHEN `GET /api/v1/admin/support/orphaned-work-items` is called
THEN only non-terminal items (state not in `ready`, `archived`, `cancelled`) with a suspended or deleted owner are returned

WHEN `POST /api/v1/admin/support/reassign-owner` is called with `new_owner_id` pointing to an inactive member
THEN the API returns HTTP 422

WHEN `POST /api/v1/admin/support/reassign-owner` is called for a terminal-state item
THEN the API returns HTTP 422

WHEN `POST /api/v1/admin/support/failed-exports/retry-all` is called
THEN the API returns HTTP 202 and all failed exports are queued

WHEN `POST /api/v1/admin/support/failed-exports/retry-all` is called a second time within 10 minutes
THEN the API returns HTTP 429

WHEN `POST /api/v1/admin/support/failed-exports/retry-all` is called while the Jira config is in `error` state
THEN the API returns HTTP 202 but the response includes a `warning` field: "Jira integration is in error state; retries may fail"

WHEN `GET /api/v1/admin/support/config-blocked-work-items` is called
THEN results are grouped by blocking reason: `suspended_owner`, `deleted_team_in_rule`, `archived_project`

## Group 10 — Phase 7: Support Tools (US-109)

- [ ] [RED] `test_orphan_detection` — elements with suspended owner, deleted owner; terminal state excluded
- [ ] [RED] `test_reassign_owner` — success, target inactive rejected, terminal element rejected, audit emitted, SSE dispatched
- [ ] [RED] `test_pending_invitations_list` — expiring soon filter, expired flag
- [ ] [RED] `test_failed_exports_list` — only failed status returned
- [ ] [RED] `test_bulk_retry` — all failed queued, rate limit enforced (429 on second call within 10 min)
- [ ] [RED] `test_bulk_retry_jira_error_warning` — warning field present when config in error state
- [ ] [RED] `test_config_blocked_elements` — suspended owner, deleted team in rule, archived project cases
- [ ] [GREEN] `application/services/support_service.py` — orphan detection, reassign, bulk retry, config-blocked detection
- [ ] [GREEN] Rate limit for `retry-all`: Redis key `retry_all:{workspace_id}` TTL 10 min
- [ ] [GREEN] Audit: owner_reassigned, jira_bulk_retry events

---

## Group 11 — Superadmin Operations

### Acceptance Criteria

WHEN `POST /api/v1/admin/users` is called by a superadmin
THEN a user row is created with the given email, display_name, and initial_capabilities[]
AND a workspace membership is created in the specified workspace
AND audit_events records `action: superadmin_user_created`

WHEN `POST /api/v1/admin/users` is called by a non-superadmin
THEN the API returns HTTP 403 with `error.code: superadmin_required` — the handler is never reached

WHEN `GET /api/v1/admin/audit/cross-workspace` is called by a non-superadmin
THEN the API returns HTTP 403

WHEN `GET /api/v1/admin/audit/cross-workspace` is called by a superadmin
THEN audit_events are returned with no workspace_id filter applied

- [ ] `presentation/dependencies/auth.py` — add `require_superadmin` FastAPI dependency (checks `user.is_superadmin`; returns 403 on failure — not 401, not 404)
- [ ] [RED] `test_require_superadmin_dependency` — superadmin passes, non-superadmin gets 403, unauthenticated gets 401
- [ ] [RED] `test_superadmin_create_user` — success, non-superadmin gets 403, duplicate email gets 409
- [ ] [RED] `test_cross_workspace_audit` — superadmin gets all workspaces, non-superadmin gets 403
- [ ] [GREEN] `POST /api/v1/admin/users` handler — calls `UserAdminService.create_user_direct()`, audit emitted
- [ ] [GREEN] `GET /api/v1/admin/audit/cross-workspace` handler — calls `AuditService.query_cross_workspace()`
- [ ] [GREEN] `app/cli.py` — `create-superadmin --email=<email>` command using Click; upserts user row with `is_superadmin=True`; prints confirmation; no HTTP involved
- [ ] [GREEN] Migration: add `is_superadmin BOOLEAN NOT NULL DEFAULT FALSE` to `users` table

---

## Group 12 — Tag Admin Integration

> Tag CRUD endpoints are implemented in EP-15. This group adds capability enforcement and audit hooks.

### Acceptance Criteria

WHEN tag CRUD operations are performed by a member with `manage_tags` capability
THEN audit_events records `action: tag_created | tag_renamed | tag_archived`

WHEN a tag merge is performed by a member without `merge_tags` capability
THEN the API returns HTTP 403

WHEN a tag merge is performed by a member with `merge_tags` capability
THEN audit_events records `action: tag_merged` with `before_value: {source_tag_id}` and `after_value: {target_tag_id}`

- [ ] [RED] `test_tag_audit_hooks` — create, rename, archive, merge each produce correct audit_event
- [ ] [RED] `test_merge_tags_capability_guard` — missing `merge_tags` gets 403, present passes
- [ ] [GREEN] Wire `manage_tags` capability guard onto EP-15's tag CRUD endpoints (decorator or dependency injection)
- [ ] [GREEN] Wire `merge_tags` capability guard onto EP-15's tag merge endpoint
- [ ] [GREEN] Audit hooks: `AuditService.record()` called within tag mutation transactions for `tag_created`, `tag_renamed`, `tag_archived`, `tag_merged`

---

## Group 13 — Puppet Integration Config

> Endpoints delegate to EP-13's `PuppetAdapter` and `PuppetConfigService`. This group owns the admin endpoint surface, capability enforcement, and audit trail.

### Acceptance Criteria

WHEN `POST /api/v1/admin/integrations/puppet` is called with valid data
THEN response is 201, `api_key` is NOT in the response body
AND credentials are Fernet-encrypted via `CredentialsStore` (same as Jira)
AND audit_events records `action: puppet_config_created` (no key values in audit)
AND a health check task is enqueued

WHEN `POST /api/v1/admin/integrations/puppet/{id}/test` is called
THEN it always returns HTTP 200 with `{ status: ok|auth_failure|unreachable, last_sync_at }`
AND `last_health_check_at` and `last_health_check_status` are updated

WHEN `GET /api/v1/admin/integrations/puppet/{id}` is called
THEN the response body contains NO `api_key` or credential field

WHEN a member without `manage_puppet_integration` capability calls any puppet endpoint
THEN the API returns HTTP 403

- [ ] [RED] `test_puppet_config_create` — success, credentials encrypted (not plaintext in DB), capability guard (403 without `manage_puppet_integration`), api_endpoint must be HTTPS
- [ ] [RED] `test_puppet_config_update_credentials` — new api_key re-encrypted, health check re-queued
- [ ] [RED] `test_puppet_connection_test` — ok, auth_failure, unreachable; always HTTP 200
- [ ] [RED] `test_puppet_credentials_never_in_response` — GET returns no credential fields
- [ ] [RED] `test_puppet_credentials_not_in_audit` — audit event for credential update has no key values
- [ ] [RED] `test_puppet_sources_crud` — add source, remove source, list sources
- [ ] [GREEN] `POST /api/v1/admin/integrations/puppet` handler
- [ ] [GREEN] `GET/PATCH /api/v1/admin/integrations/puppet/{id}` handlers
- [ ] [GREEN] `POST /api/v1/admin/integrations/puppet/{id}/test` handler — delegates to EP-13's `PuppetAdapter.probe()`
- [ ] [GREEN] `GET/POST/DELETE /api/v1/admin/integrations/puppet/{id}/sources` handlers
- [ ] [GREEN] Celery health check task for Puppet (mirrors Jira pattern: `check_puppet_health`)
- [ ] [GREEN] Audit: all Puppet config mutations call `AuditService.record()` (no credentials in payload)

---

## Group 14 — Integration & Hardening (was Group 11)

- [ ] Integration test: full member lifecycle — invite → accept → grant capability → suspend → orphan alert → reactivate
- [ ] Integration test: rule config — create workspace rule → project override → resolve precedence → blocked_override → verify project superseded
- [ ] Integration test: Jira flow — create config → test → create mapping → export → fail → retry → success
- [ ] Integration test: audit trail completeness — all mutation operations produce one audit_event each
- [ ] Verify `audit_events` UPDATE/DELETE constraints enforced (attempt mutation in test, assert no-op)
- [ ] Load test dashboard queries: 500 elements, 30 members, 10 teams — all queries < 200ms
- [ ] Verify all admin endpoints return 403 (not 401/404) when capability missing
- [ ] Grep for plaintext credentials in test fixtures and logs
