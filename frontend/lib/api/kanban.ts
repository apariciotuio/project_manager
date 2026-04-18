/**
 * EP-09 — Kanban API client.
 * GET /api/v1/work-items/kanban
 */
import { apiGet } from '../api-client';

export type KanbanGroupBy = 'state' | 'owner' | 'tag' | 'parent';

export interface KanbanCard {
  id: string;
  title: string;
  type: string;
  state: string;
  owner_id: string | null;
  completeness_score: number;
  attachment_count: number;
  tag_ids: string[];
}

export interface KanbanColumn {
  key: string;
  label: string;
  total_count: number;
  cards: KanbanCard[];
  next_cursor: string | null;
}

export interface KanbanBoard {
  columns: KanbanColumn[];
  group_by: KanbanGroupBy;
}

export interface KanbanFilters {
  group_by?: KanbanGroupBy;
  project_id?: string;
  limit?: number;
}

interface Envelope<T> {
  data: T;
}

export async function getKanbanBoard(filters: KanbanFilters = {}): Promise<KanbanBoard> {
  const params = new URLSearchParams();
  if (filters.group_by) params.set('group_by', filters.group_by);
  if (filters.project_id) params.set('project_id', filters.project_id);
  if (filters.limit !== undefined) params.set('limit', String(filters.limit));
  const qs = params.toString();
  const res = await apiGet<Envelope<KanbanBoard>>(`/api/v1/work-items/kanban${qs ? `?${qs}` : ''}`);
  return res.data;
}
