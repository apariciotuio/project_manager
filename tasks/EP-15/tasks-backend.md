# EP-15 Backend Tasks

TDD mandatory: RED → GREEN → REFACTOR. Write the failing test first.

---

## Group 1: Migrations

- [ ] **M-1** Write migration: create `tags` table with all columns and constraints
- [ ] **M-2** Write migration: create `work_item_tags` table with composite PK and FK constraints
- [ ] **M-3** Write migration: `ALTER TABLE work_items ADD COLUMN tag_ids UUID[] NOT NULL DEFAULT '{}'`
- [ ] **M-4** Write migration: partial unique index `idx_tags_workspace_slug_active`
- [ ] **M-5** Write migration: indexes `idx_tags_workspace_active`, `idx_work_item_tags_tag`, `idx_work_items_tag_ids` (GIN), `idx_tags_name_trgm` (trigram)
- [ ] **M-6** Write migration rollback for all above (Alembic downgrade)
- [ ] **M-7** Verify all migrations run cleanly on fresh DB and apply reversibly

---

## Group 2: Domain Models

- [ ] **D-1** [RED] Write test: `Tag` entity enforces slug derivation from name (lowercase, trim, spaces→dash, strip non-alphanumeric except dash)
- [ ] **D-1** [GREEN] Implement `Tag` entity in `domain/models/tag.py`
- [ ] **D-2** [RED] Write test: `Tag.archive()` transitions state; `Tag.unarchive()` raises if slug conflict check is caller's responsibility
- [ ] **D-2** [GREEN] Implement state transition methods
- [ ] **D-3** [RED] Write test: `Tag` validates color format `^#[0-9A-Fa-f]{6}$`; raises `DomainError` on invalid
- [ ] **D-3** [GREEN] Implement color validation in entity constructor / setter
- [ ] **D-4** [RED] Write test: `Tag` validates icon against predefined catalog constant
- [ ] **D-4** [GREEN] Implement icon validation; define `ICON_CATALOG` constant in `domain/constants/tag_icons.py`
- [ ] **D-5** Define `ITagRepository` interface in `domain/repositories/i_tag_repository.py`
- [ ] **D-6** Define `IWorkItemTagRepository` interface in `domain/repositories/i_work_item_tag_repository.py`
- [ ] **D-7** [REFACTOR] Review entity invariants — ensure no infrastructure leakage

---

## Group 3: TagService (CRUD + Governance)

- [ ] **S-1** [RED] Write tests: `TagService.create_tag` — success path, slug conflict 409, workspace cap 422
- [ ] **S-1** [GREEN] Implement `TagService.create_tag` in `application/services/tag_service.py`
- [ ] **S-2** [RED] Write tests: `TagService.rename_tag` — success, slug conflict, no-op when name unchanged
- [ ] **S-2** [GREEN] Implement `TagService.rename_tag`
- [ ] **S-3** [RED] Write tests: `TagService.update_tag` — color change, icon change, partial update
- [ ] **S-3** [GREEN] Implement `TagService.update_tag`
- [ ] **S-4** [RED] Write tests: `TagService.archive_tag` — success, already archived no-op
- [ ] **S-4** [GREEN] Implement `TagService.archive_tag`
- [ ] **S-5** [RED] Write tests: `TagService.unarchive_tag` — success, slug conflict on unarchive 409
- [ ] **S-5** [GREEN] Implement `TagService.unarchive_tag`
- [ ] **S-6** [RED] Write tests: `TagService.list_tags` — with/without archived filter, autocomplete query (trigram), workspace scoping
- [ ] **S-6** [GREEN] Implement `TagService.list_tags`
- [ ] **S-7** [REFACTOR] Extract slug derivation to `domain/utils/slug.py`; reuse in entity

---

## Group 4: TagAttachmentService (Attach / Detach)

- [ ] **A-1** [RED] Write tests: attach single tag — success, idempotent, archived tag 422, wrong workspace 404
- [ ] **A-1** [GREEN] Implement `TagAttachmentService.attach_tags` in `application/services/tag_attachment_service.py`
- [ ] **A-2** [RED] Write tests: attach multiple tags — all-or-nothing over limit, partial skip is NOT acceptable
- [ ] **A-2** [GREEN] Implement multi-attach atomic path
- [ ] **A-3** [RED] Write tests: `tag_ids` array sync on `work_items` — assert array updated within same transaction as `work_item_tags` insert
- [ ] **A-3** [GREEN] Implement `tag_ids` sync in `WorkItemTagRepository`
- [ ] **A-4** [RED] Write tests: detach — success, idempotent 204, wrong workspace 404
- [ ] **A-4** [GREEN] Implement `TagAttachmentService.detach_tag`
- [ ] **A-5** [RED] Write tests: bulk attach — attached_count, skipped (over limit), admin capability check
- [ ] **A-5** [GREEN] Implement `TagAttachmentService.bulk_attach`
- [ ] **A-6** [REFACTOR] Ensure all mutations go through `TagAttachmentService` — no direct repo calls from controllers

---

## Group 5: TagMergeService (Atomic Merge)

- [ ] **M-1** [RED] Write tests: merge — reassigns items, deduplicates, archives source, audit event written, single transaction
- [ ] **M-1** [GREEN] Implement `TagMergeService.merge` in `application/services/tag_merge_service.py`
- [ ] **M-2** [RED] Write tests: merge same tag → 400, target archived → 422, cross-workspace → 404
- [ ] **M-2** [GREEN] Implement guards
- [ ] **M-3** [RED] Write test: merge is idempotent — re-running after simulated partial failure produces correct state
- [ ] **M-3** [GREEN] Verify ON CONFLICT DO NOTHING semantics in repo layer
- [ ] **M-4** [REFACTOR] Verify transaction boundary covers all 4 steps (reassign, dedup, tag_ids sync, archive source)

---

## Group 6: Infrastructure Repositories

- [ ] **R-1** Implement `TagRepository` (SQLAlchemy async): create, get_by_id, get_by_slug, list_workspace_tags (with trigram search), count_active_by_workspace
- [ ] **R-2** Implement `WorkItemTagRepository`: attach (ON CONFLICT DO NOTHING), detach, bulk_attach, get_tags_for_item, sync_tag_ids_array
- [ ] **R-3** [RED] Write integration tests against real PostgreSQL (test DB): unique constraint enforcement, GIN index query, trigram search
- [ ] **R-3** [GREEN] Fix any query issues surfaced by integration tests
- [ ] **R-4** Implement `TagMergeRepository`: bulk UPDATE work_item_tags, DELETE duplicates, UPDATE work_items.tag_ids for affected items

---

## Group 7: Controllers

- [ ] **C-1** Implement `TagController` with routes:
  - `GET /api/v1/tags` — list (autocomplete + archived filter)
  - `GET /api/v1/tags/icons` — icon catalog
  - `POST /api/v1/tags` — create (requires `tags:admin`)
  - `PATCH /api/v1/tags/:id` — update/rename/archive (requires `tags:admin`)
  - `POST /api/v1/tags/:id/merge-into/:target_id` — merge (requires `tags:admin`)
- [ ] **C-2** Implement `WorkItemTagController` with routes:
  - `POST /api/v1/work-items/:id/tags` — attach
  - `DELETE /api/v1/work-items/:id/tags/:tag_id` — detach
  - `POST /api/v1/tags/:id/bulk-attach` — bulk attach (requires `tags:admin`)
- [ ] **C-3** [RED] Write controller tests: request/response serialization, 4xx error mapping, workspace scoping from auth context
- [ ] **C-4** Add `tag_ids` and `tag_mode` to EP-09 list filter schema; extend existing `WorkItemListController`

---

## Group 8: Tests (Integration + Coverage)

- [ ] **T-1** Integration test: full attach → filter → detach cycle against real DB
- [ ] **T-2** Integration test: merge flow — verify `work_item_tags`, `work_items.tag_ids`, and `audit_events` after merge
- [ ] **T-3** Performance test: list with AND-mode GIN filter on 10k items — assert p95 < 300ms
- [ ] **T-4** Test: workspace isolation — tag from workspace A cannot be attached to item in workspace B
- [ ] **T-5** Test: reconciliation logic — detect drift between `work_item_tags` and `work_items.tag_ids`

---

## Acceptance Criteria

- All mutations (attach/detach/merge) keep `work_items.tag_ids` in sync within the same transaction
- No direct DB access from controllers; all business logic in services
- Workspace scoping enforced at service layer via JWT auth context
- All admin operations produce `audit_events` rows
- GIN-indexed AND/OR filter queries perform under 300ms at p95 on 10k items
- Tag uniqueness (slug) enforced by partial unique index AND service-layer guard
