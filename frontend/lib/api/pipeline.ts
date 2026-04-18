/**
 * EP-09 — Pipeline API client.
 * GET /api/v1/pipeline
 */
import { apiGet } from '../api-client';

export interface PipelineItem {
  id: string;
  title: string;
  type: string;
  state: string;
  owner_id: string;
  completeness_score: number;
}

export interface PipelineColumn {
  state: string;
  count: number;
  avg_age_days: number;
  items: PipelineItem[];
}

export interface PipelineBoard {
  columns: PipelineColumn[];
  blocked_lane: PipelineItem[];
}

export interface PipelineFilters {
  project_id?: string;
  team_id?: string;
  owner_id?: string;
  state?: string[];
}

interface Envelope<T> {
  data: T;
}

export async function getPipeline(filters: PipelineFilters = {}): Promise<PipelineBoard> {
  const params = new URLSearchParams();
  if (filters.project_id) params.set('project_id', filters.project_id);
  if (filters.team_id) params.set('team_id', filters.team_id);
  if (filters.owner_id) params.set('owner_id', filters.owner_id);
  if (filters.state) {
    for (const s of filters.state) params.append('state', s);
  }
  const qs = params.toString();
  const res = await apiGet<Envelope<PipelineBoard>>(`/api/v1/pipeline${qs ? `?${qs}` : ''}`);
  return res.data;
}
