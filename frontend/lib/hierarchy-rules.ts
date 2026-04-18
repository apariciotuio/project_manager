/**
 * EP-14 — Frontend hierarchy parent-type rules.
 * Derived from backend HIERARCHY_RULES in work_item_type.py (parent → children dict),
 * inverted to child → valid parents.
 *
 * Value semantics:
 *   []   → no parent allowed (root types: milestone, idea, business_change)
 *   [...] → restricted to these parent types
 */
import type { WorkItemType } from './types/work-item';

export const VALID_PARENT_TYPES: Record<WorkItemType, WorkItemType[]> = {
  milestone:       [],                              // root — no parent
  idea:            [],                              // root — no parent
  business_change: [],                              // root — no parent
  initiative:      ['milestone'],
  story:           ['milestone', 'initiative'],
  enhancement:     ['milestone', 'initiative'],
  requirement:     ['initiative'],
  bug:             ['initiative', 'story'],
  task:            ['initiative', 'story'],
  spike:           ['story'],
};

/**
 * Returns the list of valid parent types for a given child type.
 * Returns [] if no parent is allowed (root types: milestone, idea, business_change).
 * Returns non-empty array with the allowed parent types otherwise.
 */
export function getValidParentTypes(childType: WorkItemType): WorkItemType[] {
  return VALID_PARENT_TYPES[childType];
}
