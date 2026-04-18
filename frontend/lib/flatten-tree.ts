/**
 * EP-14 — Tree flattening utility for virtualised TreeView.
 * Pure function — no side effects.
 */
import type { WorkItemTreeNode } from './types/hierarchy';

export interface FlatRow {
  node: WorkItemTreeNode;
  depth: number;
}

/**
 * Flattens a tree of WorkItemTreeNodes into a flat array of rows.
 *
 * @param roots     - Root nodes of the tree.
 * @param expandedIds - Set of node IDs that are currently expanded.
 * @returns         Ordered flat list of visible rows with their depth.
 */
export function flattenTree(
  roots: WorkItemTreeNode[],
  expandedIds: Set<string>,
): FlatRow[] {
  const result: FlatRow[] = [];

  function walk(nodes: WorkItemTreeNode[], depth: number): void {
    for (const node of nodes) {
      result.push({ node, depth });
      if (expandedIds.has(node.id) && node.children.length > 0) {
        walk(node.children, depth + 1);
      }
    }
  }

  walk(roots, 0);
  return result;
}
