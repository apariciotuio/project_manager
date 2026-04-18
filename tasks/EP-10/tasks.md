# EP-10 — Implementation Checklist

**Epic**: Configuration, Projects, Rules & Administration
**Status**: PARTIAL (2026-04-18) — 24/123 FE items shipped (Projects, Integrations, Tags, Puppet, Health tabs). Blocked on 8 BE gaps: admin/members, admin/rules, admin/jira, admin/support, admin/context-presets, admin dashboard, DELETE integrations/configs/{id}, admin shell.
**Last updated**: 2026-04-18

---

## Phase 0 — Foundation (Shared Infrastructure)

### Schema & Migrations
- [ ] Migration: add `capabilities text[]` and `context_labels text[]` to `workspace_memberships`
- [ ] Migration: create `invitations` table (email, token_hash, expires_at, state, context_labels, team_ids, created_by)
- [ ] Migration: create `validation_rules` table with all fields and GIN/btree indexes
- [ ] Migration: create `routing_rules` table with all fields and indexes
- [ ] Migration: create `projects` table (name, description, state, team_ids, context_preset_id, template_bindings jsonb)
- [ ] Migration: create `context_sources` table (project_id nullable, preset_id nullable, type, label, url, description, active)
- [ ] Migration: create `context_presets` table (workspace_id, name, description)
- [ ] Migration: create `jira_configs` table (workspace_id, project_id nullable, base_url, auth_type, credentials_ref, state, health fields)
- [ ] Migration: create `jira_project_mappings` table
- [ ] `audit_events` table is created in EP-00 (shared unified table, see EP-00 design.md §audit_events). EP-10 only writes with `category IN ('admin','domain')` — do NOT create the table or its PG RULEs here. Do NOT create `sync_logs` (decision #26).
- [ ] Verify all foreign keys, NOT NULL constraints, and enum constraints are in place

### Domain Models
- [ ] `domain/models/workspace_member.py` — add `Capability` enum, `MemberState` enum, `ContextLabel` enum; update `WorkspaceMember` entity
- [ ] `domain/models/invitation.py` — `Invitation` entity, `InvitationState` enum
- [ ] `domain/models/validation_rule.py` — `ValidationRule`, `Enforcement`, `ElementType` enums
- [ ] `domain/models/routing_rule.py` — `RoutingRule`
- [ ] `domain/models/project.py` — `Project`, `ProjectState`, `ContextSource`, `ContextPreset`, `TemplateBinding`
- [ ] `domain/models/jira_config.py` — `JiraConfig`, `JiraProjectMapping`, `JiraHealthStatus` (no `JiraSyncLog` — decision #26 removed sync logs)
- [ ] `domain/models/audit_event.py` — `AuditEvent` (immutable value object; no setters)

### Repository Interfaces
- [ ] `domain/repositories/workspace_member_repo.py` — interface with get_by_id, get_by_workspace, get_teamless, update_capabilities, update_state
- [ ] `domain/repositories/invitation_repo.py` — interface with create, get_by_token_hash, get_by_email, update_state
- [ ] `domain/repositories/rule_repo.py` — interface for validation and routing rules CRUD + get_active(workspace_id, project_id, element_type)
- [ ] `domain/repositories/project_repo.py` — interface for project, context source, context preset CRUD
- [ ] `domain/repositories/jira_repo.py` — interface for jira_config and mappings CRUD
- [ ] `domain/repositories/audit_repo.py` — write-only interface: `record(payload)` only; no update/delete methods defined

### Shared Infrastructure
- [ ] `infrastructure/adapters/jira/credentials_store.py` — Fernet encrypt/decrypt, store/retrieve/rotate
- [ ] `infrastructure/adapters/jira/jira_client.py` — HTTP wrapper: probe(), export_element(), get_project()
- [ ] `presentation/dependencies/auth.py` — `require_capabilities(*caps)` FastAPI dependency
- [ ] `presentation/middleware/admin_base.py` — AdminBaseMiddleware: reject if zero capabilities

---

## Phase 1 — Members & Capabilities (US-105, US-106)

All steps follow RED → GREEN → REFACTOR.

### Tests First
- [ ] [RED] Unit: `test_member_service_invite` — success path, duplicate email (active), duplicate email (invited)
- [ ] [RED] Unit: `test_member_service_activation` — via invite token, expired token, no invite for email
- [ ] [RED] Unit: `test_member_service_suspend` — success, last-admin guard, orphan-owner alert queued
- [ ] [RED] Unit: `test_member_service_delete` — success, last-admin guard, session invalidation called
- [ ] [RED] Unit: `test_member_service_reactivate` — from suspended, from deleted (rejected)
- [ ] [RED] Unit: `test_grant_capabilities` — success, grant unpossessed (rejected), unknown capability (rejected)
- [ ] [RED] Unit: `test_context_labels` — set labels, empty labels, invalid label
- [ ] [RED] Unit: `test_require_capabilities_dependency` — active member with cap passes, missing cap 403, suspended member 403
- [ ] [RED] Integration: `test_invite_resend` — success, not-resendable state, new token replaces old
- [ ] [RED] Integration: `test_member_listing_filters` — by state, teamless, pagination

### Implementation
- [ ] [GREEN] `application/services/member_service.py` — invite, activate, suspend, delete, reactivate, grant_capabilities, set_context_labels
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/member_repo_impl.py`
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/invitation_repo_impl.py`
- [ ] [GREEN] `presentation/controllers/members_controller.py` — all endpoints from US-105/106 spec
- [ ] [GREEN] Celery task: send invitation email
- [ ] [GREEN] Audit integration: all member mutations emit audit events via `AuditService.record()`
- [ ] [REFACTOR] Extract orphan-owner alert to shared `AlertService`; check for duplicate patterns

---

## Phase 2 — Validation Rules & Routing (US-102, US-103)

### Tests First
- [ ] [RED] Unit: `test_rule_precedence_engine` — project overrides workspace, blocked_override always wins, no project rule falls back to workspace, no rules returns empty
- [ ] [RED] Unit: `test_validation_rule_service_create` — workspace scope, project scope, duplicate rule rejected, blocked_override rejects conflicting project rule
- [ ] [RED] Unit: `test_validation_rule_service_update` — partial update, enforcement change to blocked_override flags superseded project rules
- [ ] [RED] Unit: `test_validation_rule_delete` — no history deletes, has history rejected
- [ ] [RED] Unit: `test_routing_rule_create` — empty rule rejected, invalid team rejected
- [ ] [RED] Unit: `test_routing_suggestions` — project-first precedence, null when no rules, suspended members excluded from validator suggestions
- [ ] [RED] Unit: `test_context_labels_separation` — labels do not confer capabilities; routing uses labels; capabilities unaffected by label change
- [ ] [RED] Integration: `test_rule_list_with_precedence_annotation` — correct `effective`, `superseded_by` fields

### Implementation
- [ ] [GREEN] `application/services/rule_service.py` — CRUD for validation and routing rules
- [ ] [GREEN] `application/services/rule_precedence_service.py` — pure `resolve_validation_rules()` and `resolve_routing_suggestion()`
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/rule_repo_impl.py`
- [ ] [GREEN] `presentation/controllers/rules_controller.py`
- [ ] [GREEN] Audit integration: all rule mutations emit audit events
- [ ] [REFACTOR] Confirm rule resolution is used by element creation endpoint (EP-08 integration point); add integration test

---

## Phase 3 — Projects & Context Sources (US-100, US-101)

### Tests First
- [ ] [RED] Unit: `test_project_service_create` — success, duplicate name rejected, invalid team IDs rejected
- [ ] [RED] Unit: `test_project_context_sources` — add source, remove source (no retroactive purge), bulk replace
- [ ] [RED] Unit: `test_project_archive` — success, open-elements alert, element creation blocked in archived project
- [ ] [RED] Unit: `test_context_preset_create` — success, duplicate name rejected
- [ ] [RED] Unit: `test_context_preset_update` — sources updated, linked projects affected, warning returned
- [ ] [RED] Unit: `test_context_preset_delete` — not in use deletes, in use rejected
- [ ] [RED] Unit: `test_project_preset_link` — success, inline sources preserved, invalid preset rejected
- [ ] [RED] Unit: `test_template_binding` — binding created, default not mandatory
- [ ] [RED] Integration: `test_project_team_deletion_cascade` — team deleted, project team_ids cleaned, alert queued

### Implementation
- [ ] [GREEN] `application/services/project_service.py` — project CRUD, context source CRUD, preset CRUD, template bindings
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/project_repo_impl.py`
- [ ] [GREEN] `presentation/controllers/projects_controller.py`
- [ ] [GREEN] Audit integration: all project/preset/source mutations emit audit events
- [ ] [REFACTOR] Confirm context sources are used by enrichment service (AI layer integration point)

---

## Phase 4 — Jira Integration (US-104)

### Tests First
- [ ] [RED] Unit: `test_jira_config_create` — success, credentials encrypted (not stored plaintext), duplicate config rejected, invalid URL rejected
- [ ] [RED] Unit: `test_jira_config_update_credentials` — new credentials replace old, re-encryption, re-health-check queued
- [ ] [RED] Unit: `test_jira_connection_test` — ok response, auth failure, unreachable, always returns 200
- [ ] [RED] Unit: `test_jira_health_check_task` — ok stays active, 3 consecutive failures → error state + SSE alert
- [ ] [RED] Unit: `test_jira_health_recovery` — error → ok → active, audit event recorded
- [ ] [RED] Unit: `test_jira_project_mapping` — success, jira project key validated, default type mappings applied
- [ ] [RED] Unit: `test_jira_credentials_never_in_response` — GET config returns no credential fields
- [ ] [RED] Unit: `test_jira_credentials_not_in_audit` — audit event for credential update has no token values

### Implementation
- [ ] [GREEN] `application/services/jira_config_service.py` — CRUD, test connection, disable/enable, mapping CRUD
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/jira_repo_impl.py`
- [ ] [GREEN] `infrastructure/adapters/jira/credentials_store.py` — Fernet implementation
- [ ] [GREEN] `infrastructure/adapters/jira/jira_client.py` — probe, get_project, export_element
- [ ] [GREEN] `infrastructure/tasks/jira_health_check.py` — Celery periodic task
- [ ] [GREEN] `presentation/controllers/integration_controller.py`
- [ ] [GREEN] Audit integration: all Jira mutations emit audit events (no credentials in payload)
- [ ] [REFACTOR] Ensure `jira_export.py` Celery task uses config service for credential retrieval; no direct DB access in task

---

## Phase 5 — Audit Log (US-107)

### Tests First
- [ ] [RED] Unit: `test_audit_service_record` — inserts event within caller transaction; fields populated correctly
- [ ] [RED] Unit: `test_audit_immutability` — no update method on repo; no delete method on repo
- [ ] [RED] Unit: `test_audit_actor_display_preserved` — actor_display populated at write time from member record
- [ ] [RED] Integration: `test_audit_query_filters` — by actor_id, by action, by entity_type, by entity_id (history), by date range, combined filters
- [ ] [RED] Integration: `test_audit_pagination` — page_size respected, max 200 enforced
- [ ] [RED] Integration: `test_audit_deleted_member_display` — actor_display still shows for deleted member

### Implementation
- [ ] [GREEN] `application/services/audit_service.py` — `record(payload)` only; synchronous; no read methods (reads in repository)
- [ ] [GREEN] `infrastructure/persistence/sqlalchemy/audit_repo_impl.py` — insert only; query with filters
- [ ] [GREEN] `presentation/controllers/audit_controller.py`
- [ ] [REFACTOR] Verify every mutation service imports and calls AuditService; add integration test for one full audit trail across member invite → activate → suspend flow

---

## Phase 6 — Health Dashboard (US-108)

### Tests First
- [ ] [RED] Unit: `test_workspace_health` — elements by state, critical blocks (>5 days), avg time to ready, stale reviews
- [ ] [RED] Unit: `test_org_health` — active count, teamless members, teams without lead, top loaded owners
- [ ] [RED] Unit: `test_process_health` — override rate, most skipped validations, exported vs not, blocked by type/team
- [ ] [RED] Unit: `test_integration_health` — ok state, error state, not configured, export counts
- [ ] [RED] Unit: `test_dashboard_empty_workspace` — all zeros, nulls, no error
- [ ] [RED] Unit: `test_dashboard_project_scoped` — metrics scoped to project_id
- [ ] [RED] Unit: `test_dashboard_cache` — second call within TTL hits cache; cache invalidated on relevant write
- [ ] [RED] Integration: `test_dashboard_project_admin_access` — project admin can access with project_id param

### Implementation
- [ ] [GREEN] `application/services/dashboard_service.py` — four health block methods + Redis cache layer
- [ ] [GREEN] SQL queries for each health block (raw SQLAlchemy core for aggregations — not ORM)
- [ ] [GREEN] Cache invalidation hooks: wire into member_service, rule_service, project_service, jira_config_service
- [ ] [GREEN] `presentation/controllers/dashboard_controller.py`
- [ ] [REFACTOR] Profile each aggregation query under realistic data volume (100+ elements, 20+ members); add EXPLAIN output to dev notes

---

## Phase 7 — Support Tools (US-109)

### Tests First
- [ ] [RED] Unit: `test_orphan_detection` — elements with suspended owner, deleted owner, terminal state excluded
- [ ] [RED] Unit: `test_reassign_owner` — success, target inactive rejected, terminal element rejected, audit emitted, SSE dispatched
- [ ] [RED] Unit: `test_reactivate_member` — from suspended succeeds, from deleted rejected, alerts resolved
- [ ] [RED] Unit: `test_pending_invitations_list` — expiring soon filter, expired flag
- [ ] [RED] Unit: `test_failed_exports_list` — only failed status returned
- [ ] [RED] Unit: `test_bulk_retry` — all failed queued, rate limit enforced (429 on second call within 10min)
- [ ] [RED] Unit: `test_bulk_retry_jira_error_warning` — warning field present when config in error state
- [ ] [RED] Unit: `test_config_blocked_elements` — suspended owner, deleted team in rule, archived project cases

### Implementation
- [ ] [GREEN] `application/services/support_service.py` — orphan detection, reassign, bulk retry, config-blocked detection
- [ ] [GREEN] Rate limit for `retry-all`: Redis key `retry_all:{workspace_id}` with 10-minute TTL
- [ ] [GREEN] `presentation/controllers/support_controller.py`
- [ ] [GREEN] Audit integration: owner_reassigned, jira_bulk_retry audit events
- [ ] [REFACTOR] Confirm `config_blocked_elements` query uses index on elements; check EXPLAIN

---

## Phase 8 — Integration & End-to-End

- [ ] Integration test: full member lifecycle — invite → accept → grant capability → suspend → orphan alert → reactivate
- [ ] Integration test: rule configuration — create workspace rule → create project override → resolve precedence → change to blocked_override → verify project rule superseded
- [ ] Integration test: Jira flow — create config → connection test → create mapping → element export → export fails → retry → success
- [ ] Integration test: audit trail completeness — run all mutation operations; verify audit_events table has one record per action
- [ ] Integration test: dashboard reflects real-time data — create suspended-owner scenario, verify orphan count in org_health
- [ ] End-to-end: minimal workspace bootstrap — no teams, no rules, no Jira; system operates normally; dashboard returns zeros

---

## Phase 9 — Review & Hardening

- [ ] Run `code-reviewer` agent on all EP-10 source files
- [ ] Run `review-before-push` workflow
- [ ] Verify no plaintext credentials appear in any log output (grep for test fixtures)
- [ ] Verify `audit_events` UPDATE/DELETE constraints are enforced (run test trying to modify an audit record)
- [ ] Load test dashboard queries with seed data: 500 elements, 30 members, 10 teams — all queries < 200ms
- [ ] Confirm all admin endpoints return `403` (not `401` or `404`) when capability is missing

---

## Progress Summary

| Phase | Status | Notes |
|---|---|---|
| 0 — Foundation | [ ] | |
| 1 — Members | [ ] | |
| 2 — Rules/Routing | [ ] | |
| 3 — Projects | [ ] | |
| 4 — Jira | [ ] | |
| 5 — Audit | [ ] | |
| 6 — Dashboard | [ ] | |
| 7 — Support Tools | [ ] | |
| 8 — Integration Tests | [ ] | |
| 9 — Review | [ ] | |
