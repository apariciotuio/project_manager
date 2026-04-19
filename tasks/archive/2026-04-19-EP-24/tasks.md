# EP-24 — Tasks

TDD-driven, XS scope. No divide: un solo agente (o sesión directa) lo cierra en 20-30 min.

## Status

**Phase**: Ready to start. Blocked by: lanes D + Lane 4 in progress (different files, technically non-blocking, but user requested sequential).

## Progress

- [x] Proposal drafted (2026-04-19)
- [x] `design.md` — NOT NEEDED (spec trivial; proposal cubre todas las decisiones)
- [x] Implementation (TDD) — 2026-04-19
- [x] BE: 9 parametrizes añadidas + `test_types_without_hierarchy_rules_cannot_parent` ampliado (21 tests GREEN)
- [x] FE: 8 tests en `hierarchy-rules.test.ts` (10 GREEN)
- [x] Full suites: BE 1944/1944 ✅ | FE 1670/1670 ✅
- [x] `code-reviewer` pass — 2026-04-19 (zero diff addicional; cambio es puramente additive — 2 keys a dict + 2 valores más en record)
- [x] `review-before-push` — FE+BE suites verdes, no regresiones

## Tasks

### Backend

- [ ] **[RED]** Añadir test en `backend/tests/unit/domain/test_work_item_hierarchy.py` (o crear si no existe):
  - `test_idea_accepts_spike_as_child`
  - `test_idea_accepts_task_as_child`
  - `test_idea_rejects_bug_as_child` (sigue prohibido)
  - `test_business_change_accepts_initiative_as_child`
  - `test_business_change_accepts_story_as_child`
  - `test_business_change_accepts_enhancement_as_child`
  - `test_business_change_rejects_requirement_as_child` (sigue prohibido)
- [ ] **[RED]** Confirmar los 7 tests fallan
- [ ] **[GREEN]** Editar `backend/app/domain/value_objects/work_item_type.py` — añadir 2 entradas a `HIERARCHY_RULES`:
  ```python
  WorkItemType.IDEA: {WorkItemType.SPIKE, WorkItemType.TASK},
  WorkItemType.BUSINESS_CHANGE: {
      WorkItemType.INITIATIVE,
      WorkItemType.STORY,
      WorkItemType.ENHANCEMENT,
  },
  ```
- [ ] **[GREEN]** Los 7 tests pasan; ningún test existente regresa
- [ ] **[REFACTOR]** Actualizar docstring de `HIERARCHY_RULES` si procede
- [ ] Actualizar `backend/app/domain/value_objects/work_item_type.py` header: "EP-14 hierarchy types" → añadir "EP-24: idea + business_change extended as parents"

### Frontend

- [ ] **[RED]** Actualizar `frontend/__tests__/lib/hierarchy-rules.test.ts`:
  - Cambiar `it('returns [] for idea — root type, no parent allowed', ...)` — ese test sigue igual (idea sigue siendo root-as-child)
  - Añadir test: `getValidParentTypes('task')` incluye `'idea'`
  - Añadir test: `getValidParentTypes('spike')` incluye `'idea'`
  - Añadir test: `getValidParentTypes('initiative')` incluye `'business_change'`
  - Añadir test: `getValidParentTypes('story')` incluye `'business_change'` (además de milestone, initiative)
  - Añadir test: `getValidParentTypes('enhancement')` incluye `'business_change'`
- [ ] **[RED]** Confirmar los 5 tests nuevos fallan
- [ ] **[GREEN]** Editar `frontend/lib/hierarchy-rules.ts`:
  ```ts
  initiative:      ['milestone', 'business_change'],
  story:           ['milestone', 'initiative', 'business_change'],
  enhancement:     ['milestone', 'initiative', 'business_change'],
  bug:             ['initiative', 'story'],
  task:            ['initiative', 'story', 'idea'],
  spike:           ['story', 'idea'],
  ```
- [ ] **[GREEN]** Los 5 tests nuevos pasan; los 6 existentes siguen verdes
- [ ] **[REFACTOR]** Actualizar comentario header de `hierarchy-rules.ts`: "EP-14 … EP-24 extended idea/business_change as parents"

### Integration / ParentPicker

- [ ] Buscar si `components/hierarchy/ParentPicker.tsx` hace pre-filter por tipo: confirmar que lee `VALID_PARENT_TYPES` y por tanto recoge los cambios automáticamente
- [ ] Si el ParentPicker tiene tests de render por tipo hijo, añadir test: creating `task` permite elegir parent `idea`; creating `initiative` permite elegir `business_change`

### Verification

- [ ] `uv run --frozen pytest tests/unit --tb=no -q` → 1907+ pass (no regresión)
- [ ] `npx vitest run` → 1632+ pass (no regresión)
- [ ] `npx tsc --noEmit` → sin errores nuevos en ficheros tocados
- [ ] `ruff check` + `mypy --strict` clean en `work_item_type.py`

### Archive

- [ ] Actualizar `tasks/tasks.md` con fila EP-24 completa + enlace al archive
- [ ] Mover `tasks/EP-24/` → `tasks/archive/YYYY-MM-DD-EP-24/`

## Definition of Done

- 7 tests BE + 5 tests FE nuevos, todos GREEN
- `HIERARCHY_RULES` tiene 5 keys (antes 3)
- `VALID_PARENT_TYPES` incluye `idea` como padre de `{spike, task}` y `business_change` como padre de `{initiative, story, enhancement}`
- Tests existentes siguen al 100%
- EP-24 archivado

## Estimate

**20-30 min** de ejecución real. Se puede cerrar en una sola sesión sin delegación a agente (directamente desde el hilo principal).
