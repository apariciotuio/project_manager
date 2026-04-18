# EP-05 — Breakdown, Hierarchy & Dependencies

## Business Need

Specifications need to become executable units. The system must support breaking work items into tasks and subtasks, maintaining traceability to the specification sections they came from. Dependencies between tasks must be explicit and cycle-free.

## Objectives

- Generate tasks and subtasks from specification
- Support manual editing: reorder, split, merge, rename
- Maintain traceability: task -> specification section origin
- Manage functional dependencies between tasks
- Provide unified hierarchical view (element -> tasks -> subtasks)
- Validate no circular dependencies

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-050 | Generate tasks and subtasks | Must |
| US-051 | Edit, split, merge, and reorder tasks | Must |
| US-052 | Maintain traceability between spec and breakdown | Must |
| US-053 | Manage functional dependencies | Must |
| US-054 | View unified hierarchy | Must |

## Acceptance Criteria

- WHEN breakdown is generated THEN tasks map to specification sections
- WHEN the user splits a task THEN both halves retain the spec origin link
- WHEN the user merges tasks THEN the resulting task references all original spec sections
- WHEN a dependency is added THEN the system validates no cycles exist
- WHEN viewing the hierarchy THEN element -> tasks -> subtasks are navigable in a tree
- AND reordering preserves all traceability links
- AND the breakdown origin is visible from any task

## Technical Notes

- Tree model for task hierarchy (adjacency list or nested set)
- Dependency graph with cycle detection (topological sort validation)
- Links between task_nodes and work_item_sections
- AI-assisted breakdown generation (wrapped LLM call)

## Dependencies

- EP-04 (structured specification to break down)

## Complexity Assessment

**Medium-High** — Tree manipulation, cycle detection, and traceability links are well-understood problems but need careful persistence design. Merge/split operations are the tricky part.

## Risks

- Traceability links break during merge/split
- Dependency graph becomes unmanageable for large items
- Generated breakdowns don't match user mental model
