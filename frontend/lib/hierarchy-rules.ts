/**
 * EP-14 — Frontend hierarchy parent-type rules.
 * Single source of truth — mirrors backend VALID_PARENT_TYPES dict.
 *
 * Value semantics:
 *   []   → no parent allowed (milestone)
 *   [...] → restricted to these types
 *   null → no type restriction (any parent or no parent)
 */
import type { WorkItemType } from './types/work-item';

export const VALID_PARENT_TYPES: Record<WorkItemType, WorkItemType[] | null> = {
  milestone:       [],                              // root — no parent
  initiative:      ['milestone'],
  story:           ['initiative'],
  requirement:     ['initiative', 'story'],
  enhancement:     ['initiative', 'story'],
  task:            null,                             // no restriction
  bug:             null,
  idea:            null,
  spike:           null,
  business_change: null,
};

/**
 * Returns the list of valid parent types for a given child type.
 * Returns [] if no parent is allowed (milestone).
 * Returns null if any parent type is acceptable.
 */
export function getValidParentTypes(childType: WorkItemType): WorkItemType[] | null {
  return VALID_PARENT_TYPES[childType] ?? null;
}
