// ─── Puppet Config ────────────────────────────────────────────────────────────

export type PuppetHealthStatus = 'ok' | 'error' | 'unchecked';

export interface PuppetConfig {
  id: string;
  base_url: string;
  state: string;
  last_health_check_status: PuppetHealthStatus;
  last_health_check_at: string;
  created_at: string;
}

export interface PuppetConfigResponse {
  data: PuppetConfig;
}

export interface PuppetConfigListResponse {
  data: PuppetConfig[];
}

export interface PuppetConfigCreate {
  base_url: string;
  api_key: string;
  workspace_id: string;
}

export interface PuppetConfigUpdate {
  base_url?: string;
  api_key?: string;
}

// ─── Documentation Sources ────────────────────────────────────────────────────

export type DocSourceType = 'github_repo' | 'url' | 'path';
export type DocSourceStatus = 'pending' | 'indexing' | 'indexed' | 'error';

export interface DocSource {
  id: string;
  name: string;
  source_type: DocSourceType;
  url: string;
  is_public: boolean;
  status: DocSourceStatus;
  last_indexed_at: string | null;
  item_count: number | null;
  error_message?: string;
}

export interface DocSourceResponse {
  data: DocSource;
}

export interface DocSourceListResponse {
  data: DocSource[];
}

export interface DocSourceCreate {
  workspace_id: string;
  name: string;
  source_type: DocSourceType;
  url: string;
  is_public: boolean;
}
