/**
 * EP-14 — Hierarchy domain types.
 * Mirrors backend Pydantic schemas exactly.
 */
import type { WorkItemType, WorkItemState } from './work-item';

// ─── Core summary (used in tree nodes, ancestor chain, children pages) ────────

export interface WorkItemSummary {
  id: string;
  title: string;
  type: WorkItemType;
  state: WorkItemState;
  parent_work_item_id: string | null;
  materialized_path: string;
  /** Children populated only in hierarchy endpoint tree nodes */
  children?: WorkItemTreeNode[];
}

// ─── Tree node (hierarchy endpoint) ──────────────────────────────────────────

export interface WorkItemTreeNode extends WorkItemSummary {
  children: WorkItemTreeNode[];
}

// ─── Hierarchy page (GET /projects/:id/hierarchy) ────────────────────────────

export interface HierarchyPageMeta {
  truncated: boolean;
  next_cursor: string | null;
}

export interface HierarchyPage {
  roots: WorkItemTreeNode[];
  unparented: WorkItemSummary[];
  meta: HierarchyPageMeta;
}

// ─── Ancestor chain (GET /work-items/:id/ancestors) ──────────────────────────

export type AncestorChain = WorkItemSummary[];

// ─── Children page (GET /work-items/:id/children) ────────────────────────────

export interface ChildrenPage {
  items: WorkItemSummary[];
  total: number;
  cursor: string | null;
  has_next: boolean;
}

// ─── Rollup (GET /work-items/:id/rollup) ─────────────────────────────────────

export interface RollupResult {
  /** null for leaf nodes */
  percent: number | null;
  /** true when the cache is being recomputed */
  stale: boolean;
}

// ─── Pagination params ────────────────────────────────────────────────────────

export interface PaginationParams {
  cursor?: string;
  limit?: number;
}
