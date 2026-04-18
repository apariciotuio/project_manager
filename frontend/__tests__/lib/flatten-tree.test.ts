/**
 * FE-14-08 — flatten-tree utility tests.
 */
import { describe, it, expect } from 'vitest';
import { flattenTree } from '@/lib/flatten-tree';
import type { WorkItemTreeNode } from '@/lib/types/hierarchy';

function makeNode(id: string, children: WorkItemTreeNode[] = []): WorkItemTreeNode {
  return {
    id,
    title: `Item ${id}`,
    type: 'story',
    state: 'draft',
    parent_work_item_id: null,
    materialized_path: '',
    children,
  };
}

describe('flattenTree', () => {
  it('returns [] for empty roots', () => {
    expect(flattenTree([], new Set())).toEqual([]);
  });

  it('single root, no children → [{node, depth: 0}]', () => {
    const root = makeNode('r1');
    const result = flattenTree([root], new Set(['r1']));
    expect(result).toHaveLength(1);
    expect(result[0]!.node.id).toBe('r1');
    expect(result[0]!.depth).toBe(0);
  });

  it('root with 2 children, all expanded → 3 rows in order', () => {
    const root = makeNode('r1', [makeNode('c1'), makeNode('c2')]);
    const expanded = new Set(['r1', 'c1', 'c2']);
    const result = flattenTree([root], expanded);
    expect(result).toHaveLength(3);
    expect(result[0]!.node.id).toBe('r1');
    expect(result[1]!.node.id).toBe('c1');
    expect(result[2]!.node.id).toBe('c2');
    expect(result[1]!.depth).toBe(1);
    expect(result[2]!.depth).toBe(1);
  });

  it('root with 2 children, root collapsed → 1 row (root only)', () => {
    const root = makeNode('r1', [makeNode('c1'), makeNode('c2')]);
    const result = flattenTree([root], new Set());
    expect(result).toHaveLength(1);
    expect(result[0]!.node.id).toBe('r1');
  });

  it('3-level tree, mid-level collapsed → grandchildren not in output', () => {
    const grandchild = makeNode('gc1');
    const child = makeNode('c1', [grandchild]);
    const root = makeNode('r1', [child]);
    // root expanded, child collapsed
    const expanded = new Set(['r1']);
    const result = flattenTree([root], expanded);
    expect(result).toHaveLength(2);
    expect(result[0]!.node.id).toBe('r1');
    expect(result[1]!.node.id).toBe('c1');
    expect(result[1]!.depth).toBe(1);
  });

  it('multiple roots, all expanded', () => {
    const roots = [makeNode('r1', [makeNode('c1')]), makeNode('r2')];
    const expanded = new Set(['r1', 'r2']);
    const result = flattenTree(roots, expanded);
    expect(result).toHaveLength(3);
    expect(result[0]!.node.id).toBe('r1');
    expect(result[1]!.node.id).toBe('c1');
    expect(result[2]!.node.id).toBe('r2');
  });
});
