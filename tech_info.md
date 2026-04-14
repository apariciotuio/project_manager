# Technical Information — Work Maturation Platform

Consolidated technical reference from all 20 epic designs (EP-00 through EP-19). This is the single source of truth for cross-cutting architectural decisions.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────┐     ┌──────────────────────┐
│                    Next.js Frontend                      │     │  External MCP clients │
│  (App Router, TS strict, Tailwind + shadcn/ui, SSE)     │     │  (Claude Code, CLIs,  │
│   Design system per EP-19 (tokens, i18n ES, a11y gate)  │     │   copilots…)          │
└──────────────────────┬──────────────────────────────────┘     └──────────┬───────────┘
                       │ HTTPS / REST                                       │ stdio / HTTP+SSE
                       ▼                                                    ▼
┌─────────────────────────────────────────────────────────┐     ┌──────────────────────┐
│                  FastAPI Backend (REST)                  │     │   MCP Server (EP-18) │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────┐    │     │  (Python, same repo, │
│  │Controllers│→│ Services  │→│  Domain Models      │    │     │   read-only MVP)     │
│  │(REST)     │  │(App layer)│  │(Business logic)    │    │     └──────────┬───────────┘
│  └──────────┘  └──────────┘  └────────────────────┘    │                │ in-process
│       │              │              ▲                    │◀────────────────┘ service calls
│       ▼              ▼              │                    │
│  ┌──────────────────────────────────────┐               │
│  │     Infrastructure Layer             │               │
│  │  Repos │ Adapters │ Dundun │ Puppet │ Jira │         │
│  └──────────────────────────────────────┘               │
└────────┬──────────────┬──────────────┬──────────────────┘
         │              │              │
    ┌────▼────┐   ┌─────▼─────┐  ┌────▼────┐
    │PostgreSQL│   │   Redis   │  │ Celery  │
    │  16+     │   │   7+      │  │ Workers │
    └─────────┘   └───────────┘  └─────────┘
```

**Transversal UI layer** (EP-12 + EP-19): EP-12 ships technical primitives (AppShell, BottomSheet, DataTable, EmptyState, SkeletonLoader, ErrorBoundary, SSE hook). EP-19 layers the design system on top: shadcn/ui on Radix, semantic tokens, Inter typography, shared domain components (`StateBadge`, `TypeBadge`, `PlaintextReveal`, `TypedConfirmDialog`, `CommandPalette`, …), ES-ES tuteo i18n, a11y gate (Lighthouse ≥ 95 + axe-playwright), `size-limit` perf budget. See `docs/ux-principles.md` and `tasks/EP-19/`.

## 2. Database Schema Overview

### Core Tables (EP-00, EP-01)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | User identity | id, google_sub, email, display_name, avatar_url, created_at |
| `refresh_tokens` | Session management | id, user_id, token_hash, expires_at, revoked_at |
| `workspaces` | Workspace container | id, name, slug, created_by, created_at |
| `workspace_members` | Membership + capabilities | id, workspace_id, user_id, capabilities[], context_labels[], status, invited_at, activated_at |
| `work_items` | Central entity | id, workspace_id, project_id, type, title, description, original_input, state, owner_id, has_override, override_justification, draft_data, template_id, current_version_id, state_entered_at, created_by, created_at, updated_at |

### Specification & Quality (EP-04)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `work_item_sections` | Structured spec | id, work_item_id, section_type, content, order, is_required |
| `work_item_versions` | Full snapshots | id, work_item_id, version_number, snapshot(JSONB), created_by, created_at |

### Breakdown (EP-05)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `task_nodes` | Hierarchy tree | id, work_item_id, parent_id, title, description, order, materialized_path, status |
| `task_node_section_links` | Traceability | task_node_id, section_id |
| `task_dependencies` | DAG edges | id, source_id, target_id |

### Reviews & Validations (EP-06)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `review_requests` | Review solicitation | id, work_item_id, version_id, reviewer_type(user/team), reviewer_id, team_id, validation_rule_id, status, created_by |
| `review_responses` | Review outcome | id, review_request_id, responder_id, decision(approve/reject/changes), content, created_at |
| `validation_requirements` | Checklist items | id, work_item_id, rule_id, required, status(pending/satisfied/waived) |

### Comments & Timeline (EP-07)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `comments` | General + anchored | id, work_item_id, author_id, content, parent_id, section_id, anchor_offset_start, anchor_offset_end, anchor_snapshot_text, created_at |
| `timeline_events` | Unified timeline | id, work_item_id, event_type, actor_id, actor_type(human/ai/system), payload(JSONB), created_at |

### Conversations & AI (EP-03)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `conversation_threads` | Chat threads | id, work_item_id(nullable), user_id, thread_type(element/general), created_at |
| `conversation_messages` | Thread messages | id, thread_id, role(user/assistant/system/summary), content, token_count, created_at |
| `assistant_suggestions` | AI proposals | id, work_item_id, thread_id, section_id, proposed_content, status(pending/accepted/rejected), version_number_target, created_by |

### Teams & Notifications (EP-08)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `teams` | Team groups | id, workspace_id, name, description, lead_id, is_review_target, created_at |
| `team_members` | Membership | team_id, user_id, joined_at |
| `notifications` | Event alerts | id, recipient_id, event_type, work_item_id, title, body, deeplink, status(unread/read/actioned), idempotency_key, created_at |

### Configuration & Admin (EP-10)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `projects` | Workspace spaces | id, workspace_id, name, description, status(active/archived), created_at |
| `validation_rules` | Configurable gates | id, workspace_id, project_id, element_type, validation_type, required, suggested_reviewer_type, order |
| `routing_rules` | Assignment hints | id, workspace_id, project_id, element_type, context_label, suggested_team_id, suggested_owner_id |
| `templates` | Per-type scaffolds | id, workspace_id, project_id, element_type, content(TEXT), is_default |
| `context_sources` | External references | id, project_id, source_type, name, url, metadata(JSONB) |
| `context_presets` | Reusable bundles | id, project_id, name, source_ids[] |
| `integration_configs` | Jira setup | id, workspace_id, provider, credentials_ref, base_url, status, last_health_check_at |
| `integration_project_mappings` | Internal→Jira map | id, integration_config_id, project_id, jira_project_key |
| `audit_events` | Admin audit | id, workspace_id, actor_id, actor_display, action, entity_type, entity_id, before_value(JSONB), after_value(JSONB), context, created_at |

### Export (EP-11)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `integration_exports` | Export records | id, work_item_id, version_id, integration_config_id, snapshot_data(JSONB), jira_issue_key, jira_project_key, status(pending/success/failed), exported_by, exported_at, error_message |
| `sync_logs` | Status sync history | id, export_id, jira_status, jira_status_category, internal_display_status, synced_at |

### MCP access (EP-18)

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `mcp_tokens` | MCP bearer tokens for external agents | id, workspace_id, user_id, name, lookup_key(HMAC, unique), secret_hash(argon2id), scopes[], created_by, created_at, expires_at, last_used_at, last_used_ip, revoked_at |

Indexes: `UNIQUE(lookup_key)`, `idx_mcp_tokens_ws_user_active` (partial on `revoked_at IS NULL`), `idx_mcp_tokens_expires_active` (partial). Single scope `mcp:read`. Single-workspace binding (no cross-workspace tokens). Verification caches in Redis 5 s (explicit DEL on revoke). New capability `mcp:issue` on workspace admins.

## 3. API Endpoint Inventory

### Auth (EP-00)
```
POST   /api/v1/auth/google          # OAuth callback
POST   /api/v1/auth/refresh          # Token refresh
POST   /api/v1/auth/logout           # Session termination
GET    /api/v1/auth/me               # Current user profile
```

### Work Items (EP-01, EP-02)
```
POST   /api/v1/work-items            # Create from free text
GET    /api/v1/work-items            # List with filters
GET    /api/v1/work-items/:id        # Detail (unified view)
PATCH  /api/v1/work-items/:id        # Update fields
PATCH  /api/v1/work-items/:id/draft  # Auto-save draft
POST   /api/v1/work-items/:id/transition  # State transition
POST   /api/v1/work-items/:id/force-ready # Override to Ready
POST   /api/v1/work-items/:id/reassign    # Change owner
```

### Specification (EP-04)
```
POST   /api/v1/work-items/:id/specification  # Generate structured spec
GET    /api/v1/work-items/:id/sections       # List sections
PATCH  /api/v1/work-items/:id/sections/:sid  # Edit section
GET    /api/v1/work-items/:id/completeness   # Score + gaps
GET    /api/v1/work-items/:id/next-step      # Recommendation
```

### Breakdown (EP-05)
```
POST   /api/v1/work-items/:id/tasks          # Generate breakdown
GET    /api/v1/work-items/:id/task-tree       # Hierarchical view
POST   /api/v1/tasks/:id/subtasks            # Add subtask
PATCH  /api/v1/tasks/:id                     # Edit task node
POST   /api/v1/tasks/:id/split               # Split task
POST   /api/v1/tasks/merge                   # Merge tasks
POST   /api/v1/tasks/:id/dependencies        # Add dependency
DELETE /api/v1/tasks/:id/dependencies/:did    # Remove dependency
```

### Reviews & Validations (EP-06)
```
POST   /api/v1/work-items/:id/reviews        # Request review
GET    /api/v1/work-items/:id/reviews        # List reviews
POST   /api/v1/reviews/:id/respond           # Approve/reject/changes
GET    /api/v1/work-items/:id/validations    # Validation checklist
PATCH  /api/v1/validations/:id               # Update validation status
```

### Comments & History (EP-07)
```
POST   /api/v1/work-items/:id/comments       # Add comment
GET    /api/v1/work-items/:id/comments       # List comments
PATCH  /api/v1/comments/:id                  # Edit comment
DELETE /api/v1/comments/:id                  # Delete comment
GET    /api/v1/work-items/:id/versions       # List versions
GET    /api/v1/work-items/:id/versions/:v1/diff/:v2  # Diff
GET    /api/v1/work-items/:id/timeline       # Unified timeline
```

### Conversations (EP-03)
```
POST   /api/v1/work-items/:id/threads        # Create element thread
POST   /api/v1/threads                       # Create general thread
GET    /api/v1/threads/:id/messages          # List messages
POST   /api/v1/threads/:id/messages          # Send message (SSE stream)
POST   /api/v1/work-items/:id/suggestions    # Generate suggestion (202)
PATCH  /api/v1/suggestions/:id               # Accept/reject
POST   /api/v1/work-items/:id/quick-actions  # Refinement actions
```

### Teams & Notifications (EP-08)
```
POST   /api/v1/teams                         # Create team
GET    /api/v1/teams                         # List teams
PATCH  /api/v1/teams/:id                     # Update team
POST   /api/v1/teams/:id/members             # Add member
DELETE /api/v1/teams/:id/members/:uid        # Remove member
GET    /api/v1/notifications                 # List notifications
PATCH  /api/v1/notifications/:id             # Mark read/actioned
GET    /api/v1/inbox                         # Prioritized inbox
GET    /api/v1/notifications/stream          # SSE connection
```

### Dashboards & Search (EP-09)
```
GET    /api/v1/dashboards/global             # Global metrics
GET    /api/v1/dashboards/by-owner/:id       # Per-person metrics
GET    /api/v1/dashboards/by-team/:id        # Per-team metrics
GET    /api/v1/dashboards/pipeline           # Pipeline stages
GET    /api/v1/search                        # Full-text search
```

### Admin (EP-10)
```
POST   /api/v1/admin/invitations             # Invite member
GET    /api/v1/admin/members                 # List members
PATCH  /api/v1/admin/members/:id             # Update member status/caps
POST   /api/v1/admin/validation-rules        # Create rule
PATCH  /api/v1/admin/validation-rules/:id    # Update rule
POST   /api/v1/admin/routing-rules           # Create routing rule
GET    /api/v1/admin/audit                   # Audit log
GET    /api/v1/admin/health                  # Health dashboard
POST   /api/v1/admin/support/reassign-orphans  # Reassign orphaned items
POST   /api/v1/admin/support/resend-invite/:id # Resend invitation
```

### Projects (EP-10)
```
POST   /api/v1/projects                      # Create project
GET    /api/v1/projects                      # List projects
PATCH  /api/v1/projects/:id                  # Update project
POST   /api/v1/projects/:id/context-sources  # Add context source
POST   /api/v1/projects/:id/templates        # Set template
```

### Jira Integration (EP-10, EP-11)
```
POST   /api/v1/admin/integrations/jira       # Configure Jira
GET    /api/v1/admin/integrations/jira/health # Health check
POST   /api/v1/work-items/:id/export         # Export to Jira
GET    /api/v1/work-items/:id/exports        # Export history
POST   /api/v1/exports/:id/retry             # Retry failed export
```

## 4. Middleware Stack (EP-12)

Order is load-bearing:

```
1. CorrelationIDMiddleware    # Generate/propagate X-Correlation-ID
2. RateLimitMiddleware        # Token bucket per IP (anon) / user (auth)
3. CORSMiddleware             # Origin whitelist
4. AuthMiddleware             # JWT validation, user resolution
5. CapabilityMiddleware       # require_capabilities() check
6. InputValidationMiddleware  # Pydantic model validation
```

## 5. Celery Queue Architecture

| Queue | Purpose | Concurrency |
|-------|---------|-------------|
| `default` | Notifications, audit fan-out | 4 workers |
| `llm_high` | Interactive chat responses | 2 workers |
| `llm_default` | Suggestion generation | 2 workers |
| `llm_low` | Background gap analysis, summarization | 1 worker |
| `integrations` | Jira export, sync polling, health checks | 2 workers |

## 6. Caching Strategy

| What | Key Pattern | TTL | Invalidation |
|------|------------|-----|-------------|
| Completeness score | `completeness:{work_item_id}` | Until invalidated | On section/task/review change |
| Dashboard aggregations | `dashboard:{type}:{scope_id}` | 60s | On state transition events |
| Templates | `template:{workspace_id}:{type}` | 300s | On template CRUD |
| User session data | `session:{user_id}` | 900s | On logout/suspension |
| OAuth state | `oauth_state:{state}` | 300s | Single-use (delete after validation) |

## 7. Domain Event Catalog

| Event | Produced By | Consumed By |
|-------|------------|-------------|
| `work_item.created` | EP-01 | EP-07 (timeline), EP-08 (notifications) |
| `work_item.state_changed` | EP-01 | EP-07 (timeline), EP-08 (notifications), EP-09 (dashboard cache invalidation) |
| `work_item.owner_changed` | EP-01 | EP-07 (timeline), EP-08 (notifications) |
| `work_item.section_updated` | EP-04 | EP-07 (version+timeline), EP-04 (completeness invalidation) |
| `work_item.specification_generated` | EP-04 | EP-07 (version+timeline) |
| `task_node.created` | EP-05 | EP-04 (completeness), EP-07 (timeline) |
| `task_node.updated` | EP-05 | EP-04 (completeness), EP-07 (timeline) |
| `review.requested` | EP-06 | EP-08 (notifications fan-out) |
| `review.responded` | EP-06 | EP-06 (validation update), EP-07 (timeline), EP-08 (notification to owner) |
| `validation.status_changed` | EP-06 | EP-04 (completeness), EP-07 (timeline) |
| `comment.created` | EP-07 | EP-08 (notifications), EP-09 (search index update) |
| `suggestion.generated` | EP-03 | EP-08 (notification to owner) |
| `suggestion.applied` | EP-03 | EP-04 (section update → completeness), EP-07 (version) |
| `export.completed` | EP-11 | EP-07 (timeline), EP-08 (notification) |
| `export.failed` | EP-11 | EP-08 (notification), EP-10 (admin health) |
| `member.suspended` | EP-10 | EP-01 (owner_suspended flag), EP-08 (admin alert) |
| `member.invited` | EP-10 | EP-10 (audit) |

## 8. Key Technical Decisions Summary

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Custom FSM, not library | 14 edges. `frozenset` of tuples. Zero deps, fully transparent |
| 2 | Derived state at read time | Storing creates consistency hazard when blocking conditions change |
| 3 | Single table for all types | Type-specific behavior in domain logic, not table structure |
| 4 | Full version snapshots | O(1) read, O(1) diff. TOAST handles compression. Delta = O(n) reconstruct |
| 5 | Dedicated timeline_events table | UNION ALL across 5 tables with cursor pagination is unmaintainable |
| 6 | Rule-based gap detection first | Deterministic, sync. LLM is async opt-in |
| 7 | Adjacency list + materialized path | Nested sets wrong for concurrent edits |
| 8 | Capability array, not RBAC | Hybrid roles (Team Lead + Project Admin) would need complex join logic |
| 9 | Puppet RAG as sole search backend | Full-text + semantic + prefix + saved searches all served by Puppet. SQL local is only for filters/listings/ID/dashboards. No PG FTS, no Elasticsearch. Push-on-write sync pipeline (<3s eventual consistency) |
| 10 | SSE over WebSocket | Unidirectional. WebSocket adds complexity for zero benefit |
| 11 | Cursor pagination everywhere | Offset degrades under concurrent writes |
| 12 | Jira re-export = new issue | Preserves Jira-side changes, avoids overwrite conflicts |
| 13 | `statusCategory.key` for sync | Jira status names are user-configurable; category keys are stable |
| 14 | Fernet-encrypted credentials | With rotation. Never in audit/API response |
| 15 | Three Celery queues for LLM | Priority separation prevents background jobs from starving interactive |

## 9. Project Directory Structure (Planned)

```
project-root/
├── backend/
│   ├── app/
│   │   ├── domain/
│   │   │   ├── models/          # Entities, value objects
│   │   │   └── repositories/    # Repository interfaces
│   │   ├── application/
│   │   │   ├── services/        # Business orchestration
│   │   │   └── validators/      # Input validation
│   │   ├── infrastructure/
│   │   │   ├── persistence/     # SQLAlchemy repos, mappers
│   │   │   ├── adapters/        # Jira, LLM, email adapters
│   │   │   └── cache/           # Redis cache layer
│   │   ├── presentation/
│   │   │   ├── controllers/     # FastAPI routers
│   │   │   └── middleware/      # Auth, CORS, rate limit, etc.
│   │   └── config/              # Settings, DI container
│   ├── migrations/              # Alembic migrations
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── conftest.py
├── frontend/
│   ├── app/                     # Next.js App Router pages
│   ├── components/              # React components
│   ├── lib/                     # API client, utils
│   ├── hooks/                   # Custom React hooks
│   └── styles/                  # Tailwind config
├── docker-compose.yml
├── tasks/                       # Planning artifacts
└── docs/                        # Architecture docs
```

## 10. Performance Targets

| Category | Target | Measurement |
|----------|--------|-------------|
| List APIs | < 200ms p95 | Cursor pagination, partial indexes |
| Detail view | < 300ms p95 | selectinload, no N+1 |
| Search | < 300ms p95 | PG tsvector + GIN index |
| Dashboards | < 500ms p95 | Redis cache, 60s TTL |
| Specification generation (AI) | < 10s | Async, SSE streaming |
| Suggestion generation (AI) | < 15s | 202 + polling |
| Jira export | < 5s | Async Celery job |
| SSE notification delivery | < 2s from event | Celery fan-out → SSE push |
