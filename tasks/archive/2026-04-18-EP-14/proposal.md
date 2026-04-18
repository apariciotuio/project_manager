# EP-14 — Hierarchy Expansion: Milestones, Epics, Stories

## Business Need

The current domain model has a shallow hierarchy: Workspace → Project → WorkItem → Task → Subtask. This works for refinement but doesn't represent **strategic planning levels**. Teams need to group related work under larger units:

- **Milestones** — time-bound delivery goals (e.g., "Q2 Launch")
- **Epics** — large chunks of product scope (e.g., "New onboarding flow")
- **Stories** — user-facing features within an epic (what maps to current WorkItem of type "requirement" or "enhancement")
- **Tasks / Subtasks** — execution units (already exist in EP-05)

The PRD mentions "Iniciativa" (Initiative) as a WorkItem type. Initiative ≈ Epic. But there's no way to link an Initiative to its constituent Stories, and no Milestone concept at all.

## Objectives

- Add `parent_work_item_id` to `work_items` — any work item can be parent of other work items
- Introduce two new types to the `type` enum: `milestone`, `story` (in addition to existing: idea, bug, mejora, tarea, iniciativa, spike, cambio, requisito)
- Enforce hierarchy rules per type (e.g., milestone cannot be child of story)
- Provide a hierarchy tree view: project-level dashboard showing Milestones → Epics → Stories → (existing tasks via EP-05 breakdown)
- Maintain the existing per-item breakdown (EP-05 task_nodes) as the leaf-level detail within Stories

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-140 | Add milestone and story as first-class work item types | Must |
| US-141 | Set parent work item when creating a story/epic | Must |
| US-142 | View hierarchy tree: milestones → epics → stories per project | Must |
| US-143 | Enforce hierarchy rules (type-based parent/child constraints) | Must |
| US-144 | Roll up completion status from children to parent | Should |
| US-145 | Filter list views by parent (e.g., "all stories in Epic X") | Must |

## Acceptance Criteria

- WHEN a user creates a work item with `parent_work_item_id` THEN the system validates the parent type is compatible (e.g., a story can have an epic or initiative as parent, not another story)
- WHEN a work item has children THEN it cannot be deleted without moving or archiving children first
- WHEN viewing a project THEN a hierarchy tree view shows: Milestones → Epics → Stories (collapsible per level)
- WHEN a story's state changes to Ready THEN the parent epic's rolled-up completion status is recomputed
- WHEN filtering by parent THEN the list shows all descendants (direct children or indirect)
- AND the existing task_nodes breakdown (EP-05) still works as the within-story leaf detail
- AND legacy items without parent (current model) remain valid and roll up to the project directly

## Technical Notes

- **Schema change to EP-01**: Add `parent_work_item_id UUID REFERENCES work_items(id) ON DELETE RESTRICT` to `work_items` table
- **Hierarchy validation service**: `HierarchyValidator.validate_parent(child_type, parent_type)` — pure function, rule-table:
  - `milestone`: no parent (project-level)
  - `iniciativa`: parent = milestone OR null
  - `story`: parent = iniciativa OR null
  - `requisito` / `mejora`: parent = iniciativa OR story OR null
  - `tarea` / `bug` / `idea` / `spike` / `cambio`: parent = any above OR null
- **Hierarchy levels**: Workspace → Project → Milestone → Epic/Initiative (iniciativa) → Story → Task → Subtask
- **Roll-up service**: `CompletionRollupService` — computes % complete for a parent based on children states (idempotent, cached in Redis)
- **New API endpoints**:
  - `GET /api/v1/projects/:id/hierarchy` — full tree
  - `GET /api/v1/work-items/:id/children` — direct children
  - `GET /api/v1/work-items/:id/ancestors` — parent chain
- **Materialized path** on `work_items` for O(1) ancestor queries (same pattern as EP-05 task_nodes)
- **Frontend**: Tree view component with collapsible nodes, breadcrumb showing ancestors, parent selector in creation form

## Dependencies

- EP-01 (schema change: adds parent_work_item_id column) — this is a SIGNIFICANT amendment
- EP-05 (task_nodes remain as leaf breakdown inside stories)
- EP-09 (list views need to show hierarchy context + filter by ancestor)
- EP-10 (projects table)

## Complexity Assessment

**High** — Domain model amendment, hierarchy validation, roll-up computation, tree UI. Affects EP-01, EP-04 (completeness per type), EP-05, EP-09. Must migrate existing items cleanly (parent_work_item_id = NULL by default).

## Risks

- Over-engineered if teams don't actually plan at milestone level
- Performance of hierarchy queries on deep trees (mitigated by materialized path)
- UX complexity: users may not understand which type to pick (need clear in-app guidance)
- Migration path: existing items have no parent — this is fine (null parent = project-level)
