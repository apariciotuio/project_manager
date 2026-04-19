/**
 * EP-14 — Frontend hierarchy parent-type rules (extended by EP-24).
 * Derived from backend HIERARCHY_RULES in work_item_type.py (parent → children dict),
 * inverted to child → valid parents.
 *
 * EP-24 promoted `idea` and `business_change` from pure-leaf roots to parent
 * types as well (they remain root-as-child — still no parent). Idea admits
 * research work (`spike`, `task`); business_change admits strategic children
 * (`initiative`, `story`, `enhancement`).
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
  initiative:      ['milestone', 'business_change'],
  story:           ['milestone', 'initiative', 'business_change'],
  enhancement:     ['milestone', 'initiative', 'business_change'],
  requirement:     ['initiative'],
  bug:             ['initiative', 'story'],
  task:            ['initiative', 'story', 'idea'],
  spike:           ['story', 'idea'],
};

/**
 * Returns the list of valid parent types for a given child type.
 * Returns [] if no parent is allowed (root types: milestone, idea, business_change).
 * Returns non-empty array with the allowed parent types otherwise.
 */
export function getValidParentTypes(childType: WorkItemType): WorkItemType[] {
  return VALID_PARENT_TYPES[childType];
}
