# Progress — Plan maturation → implementation

Living document. Tracks where we are in the plan refinement process. Update after every completed step so we can resume without re-reading the whole conversation history.

**Last updated:** 2026-04-14 (Final EP polish complete)

---

## Session-resumption summary (read this first if starting fresh)

### What this project is

**Work Maturation Platform** (internal Tuio product). A capa intermedia entre idea ambigua y ejecución: captura inputs vagos, los aterriza con clarificación guiada + IA, los estructura en especificaciones revisables, los desglosa en tareas, coordina revisiones asíncronas, y los lleva a estado `Ready` bajo criterio humano. Solo entonces se exportan a Jira.

**Principio rector**: antes de ejecutar, hay que definir bien. El producto NO es generador de tickets; es donde el trabajo se define bien antes de ejecutarse.

### Arquitectura final (decidida)

- **Producto interno Tuio**, VPN, Google Workspace users only
- **Scale pequeño**: <100 users, <50 workspaces, <5GB Postgres/año — sin partitioning, sin MV, sin vault externo
- **Multi-tenant** en una única deployment. `workspace_id` en toda tabla de dominio + PostgreSQL RLS
- **N workspaces por user** (workspace switcher + `session.active_workspace_id`)
- **5 perfiles de workspace** como constantes en código (Member, Team Lead, Project Admin, Integration Admin, Workspace Admin) + **Superadmin** como flag plataforma (`users.is_superadmin`)
- **Stack**: FastAPI + SQLAlchemy async + Postgres 16 · Next.js 14 App Router + Tailwind · Celery + Redis · SSE (no WebSocket salvo proxy a Dundun)
- **IA delegada a Dundun** (sistema externo agéntico Tuio). Nuestro BE tiene `DundunClient` (HTTP+WS). Ninguna LLM SDK en nuestras deps. Dundun maneja prompts (LangSmith), modelo, cost tracking, evals
- **Búsqueda delegada a Puppet** (RAG Tuio). Nuestro BE hace push-on-write a Puppet con tag `wm_<workspace_id>`. Search va directo de BE → Puppet (Dundun NO está en el path de búsqueda)
- **Integración Jira**: upsert-by-key outbound (re-export UPDATEs mismo issue) + acción user-initiated "import from Jira" (crea work_item en Borrador desde un issue existente). Sin polling, sin webhooks, sin sync automático
- **Colaboración**: base asíncrona + presencia tiempo real (indicadores, typing, "N viewing") + edit locks a nivel section. Sin co-edición simultánea (no CRDT/OT)
- **Sin email**, sin push. Solo notificaciones in-app vía SSE
- **Observability deferida**: solo stdlib logging + correlation ID middleware. Sin Sentry/Prometheus/Grafana/OTel
- **Attachments simplificados**: sin ClamAV, sin signed URLs (VPN interna). Endpoints autenticados que stream desde object storage. PDF thumbnails sí
- **Diff viewer** como core interaction: `remark` AST + `diff-match-patch`, granular accept/reject por segmento
- **Superadmins seed**: `david.aparicio@tuio.com`, `asis@tuio.com` via `SEED_SUPERADMIN_EMAILS` env var

### Qué hemos hecho en esta ronda (cronológico)

1. **Diagnóstico inicial**: detectamos que el plan era inconsistente consigo mismo (20 issues cross-epic), con assumptions no validadas, scope creciente sin control
2. **Re-framing**: dejó de ser MVP — asumimos scope completo del producto. Barrido de 166 referencias "MVP" en 54 archivos. Items Clase B (decisiones scopeadas MVP) → `decisions_pending.md` para re-decidir
3. **Track 2 — decisiones producto + técnicas**: cerrado. 32 decisiones resueltas una a una con el user. Incluye la clarificación crítica de que Dundun es la capa IA (no LiteLLM local)
4. **Track 1 — propagación a EP docs**: pendiente. Las 32 decisiones necesitan aplicarse en ~35 archivos de `tasks/EP-*/`. Este es el siguiente paso

### Qué queda

| Track | Estado | Qué es |
|---|---|---|
| Track 1 | 🟢 done | 32 decisiones propagadas a docs de las 18 épicas (2026-04-14) |
| Track 3 | 🟢 done | 20 issues auditadas. 15 resueltas por Track 1; 5 residuales arregladas aquí. Detalle en "Track 3 — Consistency fixes" abajo y en la tabla Phase status |
| Implementación | 🟡 desbloqueada | TDD, Security by Design, review workflow, las 17 épicas escalonadas — salvedad: revisar la ambigüedad FSM Spanish/English antes de arrancar EP-01 |

### Cómo arrancar una sesión nueva

1. Lee este `progress.md` (tienes el resumen arriba)
2. Lee `decisions_pending.md` — son 32 filas 🟢, todas cerradas, con la razón y qué tablas/endpoints afectan
3. Lee `assumptions.md` — es la segunda fuente de verdad (alineada con decisions_pending)
4. Mira la tabla "Track 1 — Propagation per EP" más abajo — ahí está el estado por épica
5. Arranca por la épica marcada 🔴 de mayor prioridad, o por la 🟡 si alguna quedó in-progress
6. Actualiza el estado aquí mismo al cerrar cada pieza

**Ficheros canónicos (orden de precedencia):**
1. `decisions_pending.md` — decisiones resueltas, fuente de verdad
2. `assumptions.md` — stack asumido, sincronizado con decisions_pending
3. **`tasks/implementation_plan.md`** — **plan por milestones (M0-M8), arranca aquí cuando se quiera codear**
4. `progress.md` (este) — estado de avance
5. `tech_info.md` — overview técnico
6. `docs/project_overview.md` — visión producto (ES narrativa)
7. `megadocumento_mvp_prd_admin_backlog.md` — PRD completo (ES narrativa)
8. `tasks/EP-*/` — docs por épica (design/proposal/specs/tasks-*)

**NUNCA tocar** sin confirmación: `CLAUDE.md`, `AGENTS.md`, `apm_modules/**`, `.apm/**`, `tasks/reviews/**`, `tasks/consistency_review.md`.

---

## Phase status

| Phase | Status | Notes |
|-------|--------|-------|
| MVP label sweep | ✅ done | Replaced/flagged 166 occurrences across 54 files. 30 Class B items → `decisions_pending.md` |
| Track 2 — technical decisions | ✅ done | 32 decisions resolved in `decisions_pending.md`, all 🟢 |
| **Track 1 — propagation to EP docs** | 🟢 **complete** | All 18 EPs updated; see per-EP table below |
| Track 3 — consistency fixes | 🟢 complete | 20 schema issues audited. 15 resolved indirectly by Track 1; 5 residuals fixed here (EP-08 tasks deps, EP-09 phantom state/type enums in listings spec, dashboard TTL 60→120s, pagination shape `next_cursor`→`cursor+has_next`, `element_id`→`work_item_id` in EP-10/EP-12 specs, `audit_logs`→`audit_events` unified table in EP-00 + de-dupe in EP-10). 0 marked obsolete. One broader drift flagged (not in scope): FSM enum Spanish in EP-01 design vs English everywhere else. |
| EP polish pass | ✅ done | 8 EPs polished (EP-03, EP-07, EP-09, EP-10, EP-11, EP-12, EP-13, EP-16), 0 drift remaining |

---

## Decisions resolved (quick index)

| # | Topic | Resolution summary |
|---|-------|--------------------|
| 1, 2 | Multi-tenancy | Multi-workspace + `workspace_id` + PostgreSQL RLS |
| 3 | Auth | Google OAuth only |
| 4, 9, 24, 28 | Search | Puppet RAG (our BE pushes); Dundun NOT in search path |
| 5, 12, 26 | Jira | Upsert-by-key outbound + user-initiated import inbound. No polling/webhooks |
| 6 | Users↔workspaces | N memberships per user, workspace switcher, session `active_workspace_id` |
| 7, 25 | Scale | Small internal product (<100 users, <50 workspaces, <5GB/y). No partitioning/MV/vault |
| 8 | Email | No email ever. Only in-app |
| 10, 11 | RBAC + non-goals | Capability array + 5 profiles as code constants + Superadmin platform flag. Collab = async + presence (no CRDT) |
| 13 | JWT | HS256 |
| 14 | First-login | No auto-create; workspace picker; Superadmin creates workspaces |
| 15 | Work-item model | `derived_state` materialized; `due_date` nullable; no event sourcing |
| 16 | Templates | JSON-schema typed, 3 layers (universal sections + field types + per-type templates) |
| 17 | Conversation | Per-user threads; prompts owned by Dundun |
| 18 | Diff viewer | Full diff UI (remark AST + diff-match-patch), granular accept/reject |
| 19 | Completeness engine | 0-100% granular; validator rules in DB; async via Dundun |
| 20 | Task breakdown | Cross-item deps yes; `dnd-kit`; no reverse FSM; async via Dundun |
| 21 | Review config | Editable via API/UI; event emission for observational cross-epic fan-out |
| 22 | Versioning/Timeline/Comments | Full scope (reactions, mentions, edit history, tags, outbox, SSE push, export, search) |
| 23 | Notifications | `AbstractEventBus` in-process; teams soft-delete; no email/push |
| 27 | Observability | **Deferred.** Only stdlib logging + correlation ID |
| 29 | Attachments | VPN internal → no ClamAV, no signed URLs, authenticated streaming endpoints. PDF thumbnails yes |
| 30 | Edit locking | Section-level locks + presence service (shared SSE channel) |
| 31 | Superadmin | Seed config (no CLI), `users.is_superadmin` flag, web/API panel (create workspace, list, grant, etc.) |
| 32 | **Dundun integration** | `DundunClient` (HTTP+WS) for all AI. Chat proxied through our BE. Async via callback pattern |

Full detail in `decisions_pending.md`.

---

## Track 1 — Propagation per EP

Status legend: 🔴 pending · 🟡 in progress · 🟢 done · ⚪ minor / skipped

| EP | Status | Scope of change | Files touched |
|----|--------|-----------------|----------------|
| **Cross-cutting** | 🟢 | Rename drift: `workspace_members`→`workspace_memberships`, `elements`/`items`→`work_items`, `reviews`→`review_requests`, `review_resolutions`→`review_responses`, `exported_by`→`users(id)`. State enum lowercase. Add missing columns to `work_items` | verified — only `tasks/consistency_review.md` + `tasks/reviews/*` carry the legacy names (forbidden-to-touch). EP canonical schema/FSM aligned; `exported_by`→users(id) in EP-11; `reviews`→`review_requests`/`review_responses` in EP-06/EP-08. Remaining `elements` in EP-09/10/12 prose is UI element and acceptable copy |
| EP-00 | 🟢 | No auto-create workspace; HS256 JWT; Superadmin seed config; `returnTo`; multi-workspace routing; `users.is_superadmin` | 0 files — already aligned (AD-05/AD-07 in design; bootstrap spec annotated; HS256/no RS256 documented) |
| EP-01 | 🟢 | Canonical `work_items` schema (full column list); FSM lowercase; derived_state materialized; due_date | 0 files — already canonical (design.md authoritative; FSM, schema, types all aligned with decisions_pending.md) |
| EP-02 | 🟢 | JSON-schema typed templates 3-layer; create `specs/templates/spec.md` | 2 files — specs/templates/spec.md fully rewritten with 3-layer model + JSON schema; design.md templates table now `schema JSONB` + canonical type enum |
| EP-03 | 🟢 **MAJOR** | Thin Dundun proxy; drop LLM/prompts; single `dundun` Celery queue; conversation_threads pointer to Dundun; diff viewer stays | 1 file — design.md §1-§2 fully rewritten. Polish pass (2026-04-14): tasks.md + tasks-backend.md + tasks-frontend.md now aligned — LLMProvider/PromptRegistry/AnthropicAdapter/prompt-YAML/tiktoken/token-budget/conversation_messages/summarise items dropped; replaced with DundunClient, FakeDundunClient, HMAC callback, WS proxy endpoint, single `dundun` queue, per-user threads |
| EP-04 | 🟢 | Granular 0-100%; validator rules DB-editable; spec gen via Dundun callback; archive job | 1 file — design.md: granular scoring float [0,1], validator rules via EP-06 DB table, spec gen delegated to Dundun (wm_spec_gen_agent via Celery callback), section-version archive job |
| EP-05 | 🟢 | Breakdown via Dundun; cross-item deps; `dnd-kit`; no reverse FSM | 1 file — design.md: task_dependencies (source_id/target_id + cross-item), Dundun breakdown via Celery callback, dnd-kit, unmark-done endpoint, READ COMMITTED concurrency |
| EP-06 | 🟢 | Validation rules editable via API/UI; event emission; `review_requests`/`review_responses` naming | 1 file — design.md: validation_requirements + workspace_id + is_active + admin API; cross-epic fan-out uses in-process bus + direct call |
| EP-07 | 🟢 **MAJOR** | Reactions, mentions, edit history, version tagging, outbox, SSE push, export, Puppet search for comments/timeline | 1 file — design.md: Markdown-aware diff (remark+diff-match-patch), outbox pattern for timeline, reactions/mentions/comment_versions/version_tags tables, manual versions, permanent delete, SSE push, export, per-user timeline, Puppet-indexed comment/timeline search. Polish pass: tasks-backend + tasks-frontend presigned-URL refs → authenticated streaming download endpoint |
| EP-08 | 🟢 | `AbstractEventBus`; no email; teams soft-delete; fix inbox queries | 1 file — design.md: teams soft-delete (deleted_at); AbstractEventBus + InProcessEventBus default; inbox UNION references review_requests/review_responses |
| EP-09 | 🟢 **MAJOR** | Search fully delegated to PuppetClient; drop PG FTS; `saved_searches` table | 2 files — design.md §4 rewritten (Puppet delegation, no FTS/tsvector/RRF); specs/search/spec.md fully rewritten (PuppetClient API, tag filters, saved_searches, prefix, degraded fallback). Polish pass: tasks.md + tasks-backend.md Groups 1/2/6/12 rewritten — no `search_vector`, no GIN FTS index, no tsvector composition, no `build_search_vector`, no `reindex_work_item_search_vector`. Replaced with SearchService wrapper, SavedSearchService, Puppet after-commit push hook, suggest endpoint, 503 SEARCH_UNAVAILABLE |
| EP-10 | 🟢 | 5 profiles as constants; Superadmin surface (web/API); project-scoped Jira; no partitioning/MV/vault; audit indexes | 1 file — design.md: 5 profiles + superadmin flag, Superadmin surface section, project-scoped mapping table, no MV/vault, Fernet with rotation. Polish pass: tasks.md + tasks-backend.md + tasks-frontend.md — `jira_sync_logs` migration/model/repo/test/UI refs dropped; `JiraSyncLogTable` renamed `JiraExportHistoryTable` sourced from EP-11 export events |
| EP-11 | 🟢 **MAJOR** | Jira upsert-by-key; `import-from-jira` action new; drop `sync_logs`/polling/webhooks | 4 files — design.md rewritten; specs/sync/spec.md gutted; specs/import/spec.md created. Polish pass: tasks.md + tasks-backend.md + tasks-frontend.md — SyncService/SyncTask/sync_all_active_exports/Celery Beat items dropped; ImportService + ImportController + `POST /work-items/import-from-jira` + ImportFromJiraModal added; integration tests updated for upsert-by-key |
| EP-12 | 🟢 | Drop observability (keep stdlib log + correlation ID); rename scope | 2 files — design.md + specs/observability/spec.md previously reduced. Polish pass: tasks.md + tasks-backend.md + tasks-frontend.md — Sentry/`sentry-sdk`/`@sentry/nextjs`/`product_events`/ProductEventService/`integration_sync_log`/`v_endpoint_metrics`/ops queue-depth + integration-health endpoints/ops dashboard page removed (not flagged). Kept: CorrelationIDMiddleware, stdlib logging, ErrorBoundary showing correlation_id |
| EP-13 | 🟢 **MAJOR** | PuppetClient + push-on-write pipeline; saved searches, faceted, prefix; drop RRF hybrid | 1 file — design.md: scope note + arch rewrite (earlier round). Polish pass: proposal.md fully rewritten (frames EP-13 as "Puppet integration — search + sync pipeline"); tasks-backend.md Groups 4/5/9/10 rewritten — HybridSearchService/RRF fusion/DocSearchService/DocContentService/ProvenanceBadge/ModeToggle dropped; SearchService thin wrapper + SavedSearchService + prefix endpoint + Puppet-health endpoint added; tasks-frontend.md rewritten — API contract + Group 1 (search bar with type-ahead) + Group 2 (result list) + Group 2b (saved searches). No hybrid/keyword/semantic mode toggle, no provenance badges, no fallback banner |
| EP-14 | 🟢 | Minor alignment with EP-01 `work_items` schema | 3 files — design+proposal types→Spanish (mejora/tarea/iniciativa/cambio/requisito); VALID_PARENT_TYPES rewritten; validation spec table canonicalized |
| EP-15 | 🟢 | Minor: cross-cutting renames + Puppet tag propagation | 1 file — design: archived→archived_at, added Puppet Search Integration + EP-13 dep |
| EP-16 | 🟢 | Drop ClamAV/signed URLs; PDF thumbnails; authenticated streaming endpoint | 2 files — design.md + security spec. Polish pass: tasks-backend.md + tasks-frontend.md fully rewritten — ClamAV Celery scan task, `attachment_scan_status`, presigned PUT/GET, `request-upload`+`confirm` two-phase flow, `useScanStatusPoller`, pending/quarantined UI states all removed. Kept: single-phase multipart upload, authenticated streaming download/`thumbnail` endpoints, PDF thumbnails via pdf2image, ImageGallery/Lightbox/PdfViewer, admin quota dashboard, comment inline images |
| EP-17 | 🟢 | Section-level locks; presence service integrated | 1 file — design.md: scope note, section-level lock key, endpoints re-scoped to /sections/:section_id/lock, admin locks GET, presence events on shared SSE channel |

---

## Track 3 — Consistency fixes (complete)

20 items in `tasks/consistency_review.md` audited 2026-04-14. Issue-by-issue:

| # | Class | Status | Action |
|---|-------|--------|--------|
| 1 | MUST | 🟢 resolved-by-track-1 | `state_entered_at` present in EP-01 design.md canonical schema |
| 2 | MUST | 🟢 resolved-by-track-1 | EP-06 explicitly notes has_override/override_justification live in EP-01; EP-06 only consumes them |
| 3 | MUST | 🟢 resolved-by-track-1 | `version_number` + `current_version_id` in EP-01 canonical schema |
| 4 | MUST | 🟢 resolved-by-track-1 | `work_item_versions` base table owned by EP-04; EP-07 ALTERs; EP-06 FK valid |
| 5 | MUST | 🟢 resolved-by-track-1 | EP-08 tasks-backend.md ALG-5/6 replaced phantom tables/states with real ones |
| 6 | MUST | 🟢 resolved-by-track-1 | All EP docs use `workspace_memberships` |
| 7 | MUST | 🟢 resolved-by-track-1 | `team_id` in EP-01 canonical schema |
| 8 | SHOULD | 🔴 fixed-now | EP-09 listings/spec.md had phantom UPPER_CASE states + phantom types (EPIC/RFC/ADR) — replaced with canonical EP-01 enums |
| 9 | SHOULD | 🔴 fixed-now | `element_id`/`element_title` → `work_item_id`/`work_item_title` in EP-10 admin-ops + integration specs + EP-12 performance spec |
| 10 | SHOULD | 🟢 resolved-by-track-1 | EP-04 + EP-07 document single-writer invariant via VersioningService |
| 11 | SHOULD | 🟢 resolved-by-track-1 | No EP doc references `reviews`/`review_resolutions` tables |
| 12 | SHOULD | 🔴 fixed-now | EP-09 dashboards/spec.md TTL 60s → 120s (EP-12 canonical) in 3 places |
| 13 | SHOULD | 🔴 fixed-now | EP-09 listings/spec.md + design.md kanban: `next_cursor` → `{cursor, has_next}` |
| 14 | SHOULD | 🟢 resolved-by-track-1 | EP-00 marks `role` as display label; EP-10 owns capabilities |
| 15 | SHOULD | 🟢 resolved-by-track-1 | EP-08 explicitly documents shared SSE channel patterns (user/workspace/work_item) + auth rules |
| 16 | SHOULD | 🟢 resolved-by-track-1 | EP-06 delegates ready transition to EP-01 generic endpoint; single FSM owner |
| 17 | SHOULD | 🟢 resolved-by-track-1 | EP-11 `exported_by` references `users(id)` |
| 18 | NITPICK | 🟢 resolved-by-track-1 | EP-03 design.md explicitly assigns `/gaps` to EP-04 (completeness) and routes content findings through `assistant_suggestions` |
| 19 | NITPICK | 🔴 fixed-now | EP-00 tasks/tasks-backend still said `audit_logs`; EP-10 tasks duplicated table creation. Unified on `audit_events` with `category` column. Ownership stays in EP-00. |
| 20 | NITPICK | 🟢 resolved-by-track-1 | Same as #18 — EP-03 cedes `/gaps` path to EP-04 |

**Totals**: 15 resolved-by-track-1, 5 fixed-now, 0 obsolete.

- FSM state enum normalized to English (`draft` / `in_clarification` / `in_review` / `changes_requested` / `partially_validated` / `ready` / `exported`, derived `in_progress` / `blocked` / `ready`); Spanish reserved for user-facing prose and UI i18n (`docs/project_overview.md`, `megadocumento_mvp_prd_admin_backlog.md`, frontend strings).

**Ambiguity flagged (out of scope for the 20-issue audit)**: The FSM state enum has conflicting canonical sources.
- `progress.md` prior summary + EP-01 `design.md` Python enum + `work_items` CHECK constraint list Spanish values: `draft`, `in_clarification`, `in_review`, `changes_requested`, `partially_validated`, `ready`, `exported` (normalized to English 2026-04-14; see bullet below).
- EP-01 `specs/state-machine/spec.md`, EP-01 `tasks-frontend.md`, and every other EP doc that references state values (EP-09, EP-06, EP-08, EP-04, EP-14, EP-17, etc.) use English: `draft`, `in_clarification`, `in_review`, `changes_requested`, `partially_validated`, `ready`, `exported`.
- Neither was a listed issue in `consistency_review.md` — the original issue #8 was just "snake_case vs UPPER_CASE", which is clean now.
- **Needs human decision before EP-01 implementation begins**: pick one language and sweep.

---

## How to resume

**If Track 1 was interrupted mid-EP:** check the "Track 1" table above for status markers. The EP marked 🟡 is where to resume. Re-read that EP's files + this `progress.md` + the relevant rows in `decisions_pending.md` to re-establish context, then continue.

**If Track 1 is done:** move to Track 3 consistency review and sweep residual schema issues.

**Invariants to preserve:**
- Never re-resolve a 🟢 decision in `decisions_pending.md` without explicit user request
- `decisions_pending.md` + `assumptions.md` are authoritative — EP docs align to them, not the reverse
- Keep `⚠️ originally MVP-scoped — see decisions_pending.md` markers in place (they're already consistent)
- Don't touch `CLAUDE.md`, `AGENTS.md`, `apm_modules/**`, `.apm/**`, `tasks/consistency_review.md`, `tasks/tasks.md`, `tasks/reviews/**`
