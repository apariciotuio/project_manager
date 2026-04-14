# Assumptions

Assumptions made during the technical planning of the MVP. These need product/business confirmation before implementation begins. Grouped by area.

---

## Tech Stack (not specified in PRD — assumed)

| Decision | Assumed | Rationale |
|----------|---------|-----------|
| Backend language | Python 3.12+ | Tuio ecosystem, LLM integration ergonomics |
| Backend framework | FastAPI (async) | Modern async support, OpenAPI auto-gen, dependency injection |
| ORM | SQLAlchemy 2.0 (async) | Mature, DDD-friendly, async sessions |
| Database | PostgreSQL 16+ | JSONB for snapshots, tsvector for FTS, mature ecosystem |
| Frontend framework | Next.js 14+ (App Router) | SSR/SSG, TypeScript, React ecosystem |
| Frontend language | TypeScript (strict mode) | Type safety, DDD alignment |
| Cache | Redis 7+ | Session store, cache, Celery broker, SSE state |
| Background jobs | Celery + Redis broker | Notification fan-out, LLM calls, export jobs, sync polling |
| Real-time delivery | SSE (Server-Sent Events) | Unidirectional push for notifications — simpler than WebSocket |
| CSS framework | Tailwind CSS | Mobile-first responsive, utility classes |
| Auth provider | Google OAuth 2.0 only (MVP) | PRD specifies Google OAuth |
| Error tracking | Sentry | Industry standard, SDK for Python + Next.js |
| LLM provider | External via adapter (Claude/OpenAI) | Wrapped behind adapter — provider-swappable |

## Architecture

| Assumption | Detail |
|------------|--------|
| Monorepo structure | `backend/` and `frontend/` in same repository |
| DDD layered architecture | Presentation → Application → Domain → Infrastructure |
| API versioning | REST with `/api/v1/` prefix |
| Single workspace per deployment (MVP) | Multi-workspace routing deferred post-MVP |
| Single-tenant | No workspace isolation at DB level in MVP |

## Authentication & Sessions

| Assumption | Detail |
|------------|--------|
| Hybrid JWT | 15-min access token (stateless) + 30-day refresh token (hashed in DB) |
| PKCE required | OAuth 2.1 compliance for browser-initiated flows |
| User identity | Resolved by `google_sub`, NOT email (email can change) |
| Workspace bootstrap | First login auto-creates personal workspace + membership in one transaction |
| Session scope | Refresh token scoped to `/api/v1/auth/refresh` path only |

## Domain Model

| Assumption | Detail |
|------------|--------|
| Single table for all types | `work_items` table with `type` column, no per-type tables |
| Custom FSM | 14-edge state machine, no external library. Transition graph as `frozenset` of tuples |
| Derived state computed, not stored | Computed from primary state + pending validations at read time |
| Override on work_item row | `has_override` + `override_justification` columns, not just in audit |
| Suspended owner → blocked | Items not auto-reassigned; admin must intervene |
| Content gate for review | Only non-empty title + description required to enter In Review |

## Versioning & History

| Assumption | Detail |
|------------|--------|
| Full snapshots over deltas | JSONB snapshot per version — O(1) read, PG TOAST handles compression |
| Timeline as dedicated table | `timeline_events` table with write-side fan-in, not UNION ALL query |
| Diff computed on demand | `difflib` stdlib, not persisted. Structured + text diff in <500ms |
| Anchor stability | By `section_id` (UUID, stable) + best-effort text offset re-computation |

## Conversations & AI

| Assumption | Detail |
|------------|--------|
| Gap detection: rule-based first | Deterministic, runs synchronously. LLM-enhanced is async and opt-in |
| Context window managed server-side | Oldest messages summarized; LLM gets summary + recent messages |
| Three Celery queues | `llm_high` (interactive), `llm_default`, `llm_low` (background analysis) |
| SSE for streaming chat | 202+poll for suggestion generation (needs full JSON before preview) |

## Teams & Notifications

| Assumption | Detail |
|------------|--------|
| SSE over WebSocket | Unidirectional push. Revisit only if collaborative editing lands |
| Inbox is computed, not materialized | UNION query with partial indexes — acceptable up to ~1k items/user |
| Notification idempotency | `sha256(recipient_id + domain_event_id)` as dedup key |
| Team review race condition | `SELECT FOR UPDATE` on review row at DB level |

## Search & Dashboards

| Assumption | Detail |
|------------|--------|
| PostgreSQL FTS | `tsvector`/`tsquery` with GIN index. No Elasticsearch for MVP |
| Cursor-based pagination everywhere | Offset pagination banned — degrades under concurrent writes |
| Dashboard: on-demand SQL + Redis cache | 60s TTL, event-driven invalidation on state transitions |
| Denormalized search columns | `aggregated_comment_text`, `aggregated_task_text` on `work_items` |

## Permissions

| Assumption | Detail |
|------------|--------|
| Capability array, not RBAC | `capabilities: text[]` on `workspace_member`. No role-permission join tables |
| `require_capabilities` FastAPI dependency | Middleware-level enforcement, not per-controller |
| Context labels separate from permissions | Labels (product, dev, QA, business) are tags, never grant operational access |

## Jira Integration

| Assumption | Detail |
|------------|--------|
| Re-export creates new Jira issue | Not update. Avoids overwriting Jira-side changes |
| Retry reuses original snapshot | Never rebuilds — snapshot is the contract |
| Status sync via `statusCategory.key` | Not status name (user-configurable per instance) |
| Fernet-encrypted credentials | With rotation path. Never in audit log or API response |
| Polling for sync (MVP) | Webhook upgrade path exists but not MVP |

## Security & Performance

| Assumption | Detail |
|------------|--------|
| Middleware chain order | Correlation ID → Rate limit → CORS → Auth → Capability check → Input validation |
| CSRF via SameSite=Strict | Explicit CSRF tokens only for cross-subdomain scenarios |
| Response time targets | List APIs <200ms, Detail <300ms, Search <300ms, Dashboard <500ms |
| Product events in PostgreSQL | Append-only table. External analytics (PostHog) deferred |

## Open Product Questions (Need Confirmation)

| # | Question | Default Assumed | Impact if Wrong |
|---|----------|----------------|-----------------|
| 1 | New user hits system with existing workspaces — auto-create personal workspace or join existing? | Auto-create personal | Changes bootstrap service logic + onboarding UX |
| 2 | Who can export to Jira? | Owner only, delegable by admin | Changes export permission check |
| 3 | Post-export element changes — notify team of divergence? | Show divergence indicator, no notification | Changes notification event list |
| 4 | Multiple workspaces per user? | One workspace per deployment (MVP) | Changes routing, DB scoping, auth resolution |
| 5 | Max elements per workspace (MVP scale target)? | 10K work items, 100K tasks | Affects index strategy, search, dashboard queries |
| 6 | LLM provider preference? | Provider-agnostic via adapter | Affects prompt engineering, token counting lib |
| 7 | Email notifications? | Not in MVP (internal notifications only) | No SMTP/SES infra needed |
| 8 | File attachments on elements? | Not in MVP | No object storage needed |
