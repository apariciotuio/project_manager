/**
 * EP-13 — Puppet Search & Doc types.
 */

// ─── Search ───────────────────────────────────────────────────────────────────

export type SearchEntityType = 'work_item' | 'section' | 'comment' | 'task' | 'doc';

export interface PuppetSearchResult {
  id: string;
  entity_type: SearchEntityType;
  title: string;
  type?: string;      // work_item only
  state?: string;     // work_item only
  score: number;
  snippet: string;
  workspace_id: string;
}

export interface PuppetSearchResponse {
  data: PuppetSearchResult[];
  pagination: {
    cursor: string | null;
    has_next: boolean;
  };
  meta: {
    puppet_latency_ms: number;
  };
}

export interface PuppetSearchParams {
  q: string;
  cursor?: string;
  limit?: number;
  state?: string;
  type?: string;
  team_id?: string;
  owner_id?: string;
  include_archived?: boolean;
}

// ─── Related Docs ─────────────────────────────────────────────────────────────

export interface RelatedDoc {
  doc_id: string;
  title: string;
  source_name: string;
  snippet: string;
  url: string;
  score: number;
}

export interface RelatedDocsResponse {
  data: RelatedDoc[];
}

// ─── Doc Content ──────────────────────────────────────────────────────────────

export interface DocContent {
  doc_id: string;
  title: string;
  content_html: string;
  url: string;
  source_name: string;
  last_indexed_at: string;
  content_truncated?: boolean;
}

export interface DocContentResponse {
  data: DocContent;
}
