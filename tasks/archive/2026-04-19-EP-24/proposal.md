# EP-24 — Hierarchy expansion: allow `idea` and `business_change` as parent types

## Business Need

Conversación con el usuario (2026-04-19) identificó dos gaps del modelo de jerarquía introducido por EP-14:

1. **`idea` es un root huérfano sin hijos**. Los usuarios que quieren hacer research previo a promover una idea a iniciativa hoy se ven obligados a crear `spike`s/`task`s huérfanos. No hay contenedor de discovery.
2. **`business_change` también es root huérfano**. Muchos equipos lo usan conceptualmente como "epic de negocio" que agrupa iniciativas (ej. "Migrar a nuevo CRM"). Hoy el único root con estructura es `milestone`, que semánticamente es un **hito temporal**, no un **cambio organizativo**. Hay conflación forzada.

La decisión EP-14 de mantener `idea`/`business_change` como roots aislados fue deliberada (separación discovery vs delivery), pero dejó estos dos gaps funcionales que los usuarios ya están workarounding.

## Scope — Opción D

Añadir 2 entradas nuevas al `HIERARCHY_RULES` de BE (y el inverso en FE), **zero-removal**:

| Padre nuevo | Hijos permitidos |
|---|---|
| `idea` | `spike`, `task` |
| `business_change` | `initiative`, `story`, `enhancement` |

## Semántica resultante

### Padre → Hijos permitidos (BE `HIERARCHY_RULES`)

| Padre | Hijos |
|---|---|
| `milestone` | `initiative`, `story`, `enhancement` |
| `initiative` | `story`, `requirement`, `enhancement`, `bug`, `task` |
| `story` | `task`, `bug`, `spike` |
| **`idea`** *(nuevo)* | `spike`, `task` |
| **`business_change`** *(nuevo)* | `initiative`, `story`, `enhancement` |

### Hijo → Padres permitidos (FE `VALID_PARENT_TYPES`)

| Hijo | Padres |
|---|---|
| `milestone` | `[]` (root, sin padre) |
| `idea` | `[]` (root, sin padre) |
| `business_change` | `[]` (root, sin padre) |
| `initiative` | `milestone`, `business_change` |
| `story` | `milestone`, `initiative`, `business_change` |
| `enhancement` | `milestone`, `initiative`, `business_change` |
| `requirement` | `initiative` |
| `bug` | `initiative`, `story` |
| `task` | `initiative`, `story`, `idea` |
| `spike` | `story`, `idea` |

### Árbol canónico

```
milestone  (root — hito temporal)
└── [initiative, story, enhancement]  (sin cambios vs EP-14)

business_change  (root — cambio estratégico, NUEVO como container)
├── initiative
│   └── [mismo subárbol que bajo milestone]
├── story
│   └── [mismo subárbol que bajo milestone]
└── enhancement

idea  (root — hipótesis, NUEVO como container de research)
├── spike
└── task
```

## Invariantes preservadas

- **Roots siguen siendo 3**: `milestone`, `idea`, `business_change`. No se añaden ni quitan roots.
- **Hojas puras**: `requirement`, `bug`, `task`, `spike`, `enhancement` siguen sin poder ser padre.
- **DAG**: no se introducen ciclos. Los "diamantes" (`story` cuelga de 3 sitios, `task` de 3, `spike` de 2) son rutas alternativas, no ciclos.
- **Backwards-compatible**: sólo añade caminos, no quita. Items existentes siguen válidos. No requiere migración de datos.

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-240 | Como PO, quiero colgar `spike`s bajo una `idea` para hacer research de validación antes de promoverla a iniciativa, de modo que el trabajo de discovery quede trazable al origen | Must |
| US-241 | Como PO, quiero colgar `task`s exploratorias bajo una `idea` sin tener que crearlas como huérfanas | Must |
| US-242 | Como líder estratégico, quiero agrupar `initiative`s bajo un `business_change` para reflejar que varias iniciativas contribuyen al mismo cambio organizativo | Must |
| US-243 | Como líder estratégico, quiero colgar `story`s y `enhancement`s directamente bajo un `business_change` cuando el alcance no justifica una iniciativa intermedia | Must |
| US-244 | Como usuario, los work items existentes con padre o sin padre siguen siendo válidos después del despliegue (backwards-compatible) | Must |

## Acceptance Criteria

### BE (`HIERARCHY_RULES`)

- WHEN se consulta `HIERARCHY_RULES[WorkItemType.IDEA]` THEN devuelve `{WorkItemType.SPIKE, WorkItemType.TASK}`
- WHEN se consulta `HIERARCHY_RULES[WorkItemType.BUSINESS_CHANGE]` THEN devuelve `{WorkItemType.INITIATIVE, WorkItemType.STORY, WorkItemType.ENHANCEMENT}`
- AND los otros 3 keys (`MILESTONE`, `INITIATIVE`, `STORY`) quedan intactos
- AND `HierarchyValidator.validate_parent(child=TASK, parent=IDEA)` devuelve válido (no lanza)
- AND `HierarchyValidator.validate_parent(child=INITIATIVE, parent=BUSINESS_CHANGE)` devuelve válido
- AND `HierarchyValidator.validate_parent(child=BUG, parent=IDEA)` SIGUE lanzando `HierarchyViolation` (no está en la lista)
- AND `HierarchyValidator.validate_parent(child=REQUIREMENT, parent=BUSINESS_CHANGE)` SIGUE lanzando `HierarchyViolation`

### FE (`VALID_PARENT_TYPES`)

- `getValidParentTypes('task')` incluye `'idea'` en la lista (además de `'initiative'`, `'story'`)
- `getValidParentTypes('spike')` incluye `'idea'` (además de `'story'`)
- `getValidParentTypes('initiative')` incluye `'business_change'` (además de `'milestone'`)
- `getValidParentTypes('story')` incluye `'business_change'`
- `getValidParentTypes('enhancement')` incluye `'business_change'`
- `getValidParentTypes('idea')` y `getValidParentTypes('business_change')` siguen devolviendo `[]` (siguen siendo root)

### E2E / no regresión

- Todos los tests existentes de jerarquía (`backend/tests/unit/domain/*hierarchy*`, `frontend/__tests__/lib/hierarchy-rules.test.ts`) siguen verdes
- `ParentPicker` FE ofrece `idea` como opción cuando el tipo hijo es `spike` o `task`
- `ParentPicker` FE ofrece `business_change` cuando el tipo hijo es `initiative`/`story`/`enhancement`

## Non-Goals

- NO se modifican los otros tipos ni sus relaciones (milestone/initiative/story quedan intactos)
- NO se migran work items existentes (backwards-compatible)
- NO se cambia la UI del creation-form más allá del `ParentPicker` consumer (los filtros/iconos/copy quedan igual)
- NO se añade `idea` o `business_change` a la hierarchy nav tree component si no estaban ya (out of scope; EP-14 la gestionó)
- NO se toca el `MaterializedPath` ni `RollupService` — funcionan sobre cualquier padre válido sin cambios

## Dependencies

- EP-14 (archivado) — este EP **extiende** `HIERARCHY_RULES` y `VALID_PARENT_TYPES` que EP-14 introdujo
- Bloqueado por: nada. Puede arrancar en cuanto terminen los lanes actuales (D + Lane 4)

## Complexity

**Trivial — XS**. 2 entradas en un dict BE + 2 entradas en un record FE + 4-6 tests nuevos (2 BE + 4 FE) + update tests existentes de `hierarchy-rules.test.ts`. Estimación: **20-30 min real time**.

## Open Questions

Ninguna pendiente. Semántica cerrada con el usuario 2026-04-19.

## Rollout

No requiere feature flag ni migración de datos. Deploy atómico — una vez mergeado, el `ParentPicker` empieza a ofrecer los nuevos caminos y el validator acepta los nuevos padres. Items existentes siguen siendo válidos tal cual.
