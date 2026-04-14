# EP-04 — Technical Design
# Structured Specification & Quality Engine

---

## 1. Data Model

### 1.1 work_item_sections

One row per section per work item. Replaces any flat JSON blob approach — this gives us queryable,
individually-versionable sections.

```sql
CREATE TABLE work_item_sections (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    section_type    VARCHAR(64) NOT NULL,  -- enum enforced at app layer
    content         TEXT NOT NULL DEFAULT '',
    display_order   SMALLINT NOT NULL,
    is_required     BOOLEAN NOT NULL DEFAULT FALSE,
    generation_source VARCHAR(16) NOT NULL DEFAULT 'llm',  -- 'llm' | 'manual' | 'revert'
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID NOT NULL REFERENCES users(id),
    updated_by      UUID NOT NULL REFERENCES users(id),

    CONSTRAINT uq_work_item_section_type UNIQUE (work_item_id, section_type)
);

CREATE INDEX idx_work_item_sections_work_item_id ON work_item_sections(work_item_id);

-- Per db_review.md IDX-6: CompletenessService filters by (work_item_id, is_required).
-- Composite covers the completeness query without hitting the heap for section_type.
CREATE INDEX idx_wis_completeness
    ON work_item_sections(work_item_id, is_required, section_type);
```

### 1.2 work_item_versions

Full-snapshot version log for the entire work item. Created on every content edit, state transition, review outcome, and breakdown change. Never update rows here.

Consumed by: EP-06 (review pinning — `review_requests.version_id` FK), EP-07 (timeline/diff — reads snapshots), and EP-11 (export snapshots).

```sql
CREATE TABLE work_item_versions (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id          UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    version_number        INTEGER NOT NULL,
    snapshot              JSONB NOT NULL,
    created_by            UUID NOT NULL REFERENCES users(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (work_item_id, version_number)
);

CREATE INDEX idx_wiv_work_item_created ON work_item_versions (work_item_id, created_at DESC);
```

### 1.3 work_item_section_versions

Append-only version log. Enables diff and revert. Never update rows here.

```sql
CREATE TABLE work_item_section_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id      UUID NOT NULL REFERENCES work_item_sections(id) ON DELETE CASCADE,
    work_item_id    UUID NOT NULL,  -- denormalized for query convenience
    section_type    VARCHAR(64) NOT NULL,
    content         TEXT NOT NULL,
    version         INTEGER NOT NULL,
    generation_source VARCHAR(16) NOT NULL,
    revert_from_version INTEGER,   -- set when generation_source = 'revert'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by      UUID NOT NULL REFERENCES users(id)
);

CREATE INDEX idx_section_versions_section_id ON work_item_section_versions(section_id);
CREATE INDEX idx_section_versions_work_item_id ON work_item_section_versions(work_item_id);
```

### 1.4 work_item_validators (for US-043 validator assignment)

```sql
CREATE TABLE work_item_validators (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    work_item_id    UUID NOT NULL REFERENCES work_items(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id),
    role            VARCHAR(64) NOT NULL,  -- 'tech_lead', 'product_owner', etc.
    status          VARCHAR(32) NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'changes_requested'
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by     UUID NOT NULL REFERENCES users(id),
    responded_at    TIMESTAMPTZ,

    CONSTRAINT uq_work_item_validator UNIQUE (work_item_id, role)
);
```

**Validator rules live in DB, not YAML/env** (resolution #19, decisions_pending.md). See EP-06 `validation_requirements` — editable via the admin API/UI. EP-04 resolves applicable rules per work-item type via `ValidationRequirementsRepository.list_active(workspace_id, work_item_type)` and renders them in the Next-Step recommender.

---

## Versioning Integration

EP-04 operates two versioning layers that serve different consumers:

1. **Section-level audit (`work_item_section_versions`)** — append-only log per section, used for section diff/revert within EP-04's own UI. Never read cross-epic.

2. **Full-snapshot versions (`work_item_versions`)** — the canonical cross-epic version. EP-04 defines the table structure. **All writes to `work_item_versions` are owned exclusively by EP-07's `VersioningService`.** No service outside `VersioningService` may INSERT into this table directly.

**Single-writer invariant**: `SectionService.save()` MUST call `VersioningService.create_version(work_item_id, trigger='content_edit', actor_id=..., actor_type='human')` instead of writing to `work_item_versions` directly. This maintains EP-07's ownership over the `trigger`, `actor_type`, and `commit_message` columns that EP-07 adds via additive migration.

**Trigger points that call `VersioningService.create_version()`:**
- `SectionService.save()` (trigger=`content_edit`) — EP-04
- `WorkItemService.transition_state()` (trigger=`state_transition`) — EP-01
- `TaskService.create()` / `delete()` (trigger=`breakdown_change`) — EP-05

EP-07 adds the `trigger`, `actor_type`, `commit_message`, `snapshot_schema_version`, and `archived` columns to `work_item_versions` via an additive migration. The base table defined here is intentionally minimal — EP-07 extends it and owns all writes.

---

## 2. Section Type Catalog

Defined as a Python enum in `domain/models/section_type.py`. The mapping from element type to section
types lives in `domain/models/section_catalog.py` as a pure dict — no DB rows, no migrations for new
section types.

```python
SECTION_CATALOG: dict[WorkItemType, list[SectionConfig]] = {
    WorkItemType.BUG: [
        SectionConfig("summary",             order=1, required=True),
        SectionConfig("steps_to_reproduce",  order=2, required=True),
        SectionConfig("expected_behavior",   order=3, required=True),
        SectionConfig("actual_behavior",     order=4, required=True),
        SectionConfig("environment",         order=5, required=False),
        SectionConfig("impact",              order=6, required=False),
        SectionConfig("acceptance_criteria", order=7, required=True),
        SectionConfig("notes",               order=8, required=False),
    ],
    # ... other types
}
```

This is the single source of truth. The spec.md section table is derived from this. Do not duplicate it.

---

## 3. Completeness Engine

### 3.1 Architecture

```
GET /work-items/:id/completeness
    → CompletenessController
        → CompletenessService.compute(work_item_id)
            → Redis.get(cache_key)
            → [miss] SectionRepository.get_by_work_item(id)
                   + ValidatorRepository.get_by_work_item(id)
                   + WorkItemRepository.get(id)
                   → DimensionChecker.check_all(work_item, sections, validators)
                   → ScoreCalculator.compute(dimension_results, work_item_type)
                   → Redis.set(cache_key, result, ttl=60)
            → return CompletenessResult
```

No business logic in the controller. `CompletenessService` lives in `application/services/`. The
dimension checkers are pure functions in `domain/quality/dimension_checkers.py` — one function per
dimension, each takes `(WorkItem, list[Section], list[Validator]) -> DimensionResult`.

### 3.2 DimensionChecker interface

```python
@dataclass
class DimensionResult:
    dimension: str
    weight: float         # renormalized for this element type
    filled: bool
    score: float          # currently 0.0 or 1.0; allow partial in future (originally MVP-scoped — see decisions_pending.md)
    message: str | None   # gap message if not filled

def check_acceptance_criteria(
    work_item: WorkItem,
    sections: list[Section],
    validators: list[Validator],
) -> DimensionResult: ...
```

Pure functions. No I/O. Trivially testable. **Granular 0.0–1.0 partial scoring is in scope** (resolution #19). Each dimension checker may return any `score ∈ [0.0, 1.0]`. `filled` is retained as a convenience flag (`score >= 1.0 → filled`). Final `completeness_score` is 0–100, computed as a weighted sum of dimension scores multiplied by renormalized weights for the section/field set applicable to this work-item type.

### 3.3 Weight renormalization

```python
def renormalize_weights(
    dimensions: list[DimensionConfig],
    applicable: set[str],
) -> dict[str, float]:
    active = [d for d in dimensions if d.name in applicable]
    total = sum(d.weight for d in active)
    # Fixed per backend_review.md ALG-4: guard zero-division when ALL dimensions are
    # inapplicable (misconfigured SECTION_CATALOG). ScoreCalculator.compute() must
    # check for empty return and return CompletenessResult(score=0, level='low', dimensions=[]).
    if total == 0.0:
        return {}
    return {d.name: d.weight / total for d in active}
```

The caller is `ScoreCalculator`. This is tested independently.

### 3.4 Gap detection

Gap detection is a filter over dimension results where `filled == False`. Severity is statically defined
in `domain/quality/gap_severity.py` — no runtime computation.

### 3.5 Caching strategy

Cache key: `completeness:{work_item_id}`
TTL: 60 seconds
Invalidation trigger (sync, within the same request/transaction callback):
- Any section `content` write (create or update)
- Work item state transition
- Validator status change

Implementation: `CompletenessCache` thin wrapper around Redis in `infrastructure/cache/`. Invalidation
is called from `SectionService.save()`, `WorkItemService.transition_state()`, and
`ValidatorService.update_status()` after their DB commits. Do NOT invalidate inside the transaction —
only after commit.

---

## 4. Next-Step Recommender

### 4.1 Architecture

```
GET /work-items/:id/next-step
    → NextStepController
        → NextStepService.recommend(work_item_id)
            → CompletenessService.compute(work_item_id)  # reuses cache
            → GapService.list(work_item_id)              # derived from completeness
            → NextStepDecisionTree.evaluate(work_item, completeness, gaps)
            → ValidatorSuggestionEngine.suggest(work_item_type, workspace_config)
            → return NextStepResult
```

`NextStepDecisionTree` is a pure function — ordered rule list, first match wins. Defined in
`domain/quality/next_step_rules.py`. No LLM. This must be fast and deterministic.

### 4.2 ValidatorSuggestionEngine

Reads active `validation_requirements` (EP-06 table, editable via admin API/UI) matching the work item's type via `applies_to`. The engine checks which rules have a resolvable reviewer in the workspace and sets `configured: bool` accordingly. No YAML/env config; rules live in the DB.

---

## 5. API Endpoints

| Method  | Path                                                     | Auth         | Notes                                        |
|---------|----------------------------------------------------------|--------------|----------------------------------------------|
| GET     | /api/v1/work-items/:id/specification                     | Bearer JWT   | Returns all sections for the work item       |
| POST    | /api/v1/work-items/:id/specification/generate            | Bearer JWT   | Triggers LLM generation, returns sections    |
| PATCH   | /api/v1/work-items/:id/sections/:section_id              | Bearer JWT   | Update single section content / order        |
| PATCH   | /api/v1/work-items/:id/sections                          | Bearer JWT   | Bulk update sections (atomic)                |
| GET     | /api/v1/work-items/:id/sections/:section_id/versions     | Bearer JWT   | Version history for a section                |
| GET     | /api/v1/work-items/:id/completeness                      | Bearer JWT   | Weighted score + dimension breakdown         |
| GET     | /api/v1/work-items/:id/gaps                              | Bearer JWT   | Gap list with severity                       |
| GET     | /api/v1/work-items/:id/next-step                         | Bearer JWT   | Next step + suggested validators             |

All endpoints require the requesting user to have at minimum read access to the work item. PATCH endpoints
additionally check owner or editor role. Authorization check happens in the service layer, not the
controller.

### 5.1 Response shapes

**GET /specification**
```json
{
  "data": {
    "work_item_id": "uuid",
    "sections": [
      {
        "id": "uuid",
        "section_type": "summary",
        "content": "...",
        "display_order": 1,
        "is_required": true,
        "generation_source": "manual",
        "version": 3,
        "updated_at": "2026-04-13T10:00:00Z",
        "updated_by": "uuid"
      }
    ]
  }
}
```

**GET /completeness**
```json
{
  "data": {
    "score": 68,
    "level": "medium",
    "dimensions": [
      {
        "name": "acceptance_criteria",
        "weight": 0.22,
        "filled": false,
        "score": 0.0,
        "contribution": 0.0
      }
    ],
    "computed_at": "2026-04-13T10:00:00Z",
    "cached": true
  }
}
```

**GET /gaps**
```json
{
  "data": [
    {
      "dimension": "acceptance_criteria",
      "message": "Define at least 2 acceptance criteria for this User Story.",
      "severity": "blocking"
    }
  ]
}
```

**GET /next-step**
```json
{
  "data": {
    "next_step": "define_acceptance_criteria",
    "message": "Add at least 2 acceptance criteria to proceed to review.",
    "blocking": true,
    "gaps_referenced": ["acceptance_criteria"],
    "suggested_validators": [
      {
        "role": "product_owner",
        "reason": "Required for User Story review.",
        "configured": true
      },
      {
        "role": "tech_lead",
        "reason": "Recommended for technical feasibility review.",
        "configured": false,
        "setup_hint": "Configure this role in workspace settings."
      }
    ]
  }
}
```

---

## 6. Integration with EP-03 (Suggestion System)

EP-03 produces `Suggestion` objects that can target either the whole element or a specific section.
EP-04 adds `section_id` as an optional foreign key on the `suggestions` table (migration via EP-04).

When a suggestion is accepted:
- If `suggestion.section_id` is set: apply the suggestion content to that section via `SectionService.save()`
- If `suggestion.section_id` is null: apply to the element's free-text description (EP-02/EP-03 behavior, unchanged)

The completeness cache is invalidated as a side effect of `SectionService.save()` — no special EP-03
coupling required.

Specification generation (US-040) is delegated to Dundun (resolution #19, #32). The controller `POST /api/v1/work-items/:id/specification/generate` enqueues a Celery task on queue `dundun`. The task calls `DundunClient.invoke_agent(agent="wm_spec_gen_agent", user_id=..., work_item_id=..., callback_url=<BE>/api/v1/dundun/callback, payload={ original_input, template_id })`. Dundun returns 202 + `request_id`; the callback handler persists the returned sections via `SectionService.save()` and emits `specification.generated` for SSE push. No LLM SDK or prompt template lives in our repo.

---

## 6.b Section-Version Archive Job

Celery periodic task `archive_stale_section_versions` runs daily. For any `work_item_section_versions` row whose `created_at` is more than 90 days older than the current section version AND which has no references (no pending reverts, not referenced by `review_requests.version_id`), the row is moved to `work_item_section_versions_archive` (same schema, tagged `archived_at`). Keeps the hot table lean without losing audit history.

---

## 7. Layer Breakdown

```
presentation/
  controllers/
    specification_controller.py     # US-040, US-041 endpoints
    completeness_controller.py      # US-042 endpoints
    next_step_controller.py         # US-043 endpoint

application/
  services/
    specification_service.py        # generate, get, save sections
    completeness_service.py         # compute, cache read/write
    gap_service.py                  # derives from completeness result
    next_step_service.py            # orchestrates decision tree + validator suggestion

domain/
  models/
    section.py                      # Section entity
    section_type.py                 # SectionType enum
    section_catalog.py              # SECTION_CATALOG dict
    dimension_result.py             # DimensionResult dataclass
  quality/
    dimension_checkers.py           # one pure function per dimension
    score_calculator.py             # renormalize + compute weighted score
    gap_severity.py                 # static severity map
    next_step_rules.py              # ordered rule list, pure evaluation
    validator_suggestion_engine.py  # type -> roles mapping, config lookup
  repositories/
    section_repository.py           # interface
    validator_repository.py         # interface

infrastructure/
  persistence/
    section_repository_impl.py
    validator_repository_impl.py
    section_version_repository_impl.py
  cache/
    completeness_cache.py           # Redis wrapper
  llm/
    prompts/
      specification_generation.py
  config/
    validator_roles.py              # load from YAML / env at startup
```

---

## 8. Performance Considerations

- Completeness is computed synchronously on GET — the query is cheap (sections + validators for one
  work item, typically < 20 rows). Redis cache absorbs repeated calls on the same element.
- Bulk section PATCH is a single transaction — avoids N partial commits.
- Section version table can grow large over time. Add a background job (deferred) to archive versions
  older than 90 days beyond the 10 most recent per section. ⚠️ originally MVP-scoped — see decisions_pending.md
- No full-table scans in any EP-04 query. All queries are by `work_item_id` (indexed).
- The LLM call in US-040 is the only slow path. It is synchronous currently (acceptable for a user-initiated
  action). If P95 latency > 5s, move to a Celery task with a polling endpoint. ⚠️ originally MVP-scoped — see decisions_pending.md

---

## 9. Alternatives Considered

**Storing completeness score in the DB**: Rejected. Score depends on section content, validators, and
state — maintaining it via triggers or application-level hooks is a consistency nightmare. Compute on
demand + cache is cleaner and cheaper to change when formula evolves.

**Single `specification` JSON column on `work_items`**: Rejected. Not queryable by section type, no
per-section versioning, forces full document overwrite on every edit. The section table design pays for
itself immediately in versioning and gap detection.

**LLM for next-step recommendation**: Rejected. Deterministic decision tree is faster, cheaper,
testable, and more reliable. LLM adds cost and non-determinism to a computation that should be
predictable and auditable.
