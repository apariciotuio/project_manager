/**
 * Shared API response types for EP-03 frontend pages.
 */

// ─── Templates ────────────────────────────────────────────────────────────────

export interface Template {
  id: string;
  name: string;
  description: string | null;
  type: string;
  fields: Record<string, unknown>;
}

export interface TemplatesResponse {
  data: Template[];
}

// ─── Drafts ───────────────────────────────────────────────────────────────────

export interface Draft {
  id: string;
  title: string | null;
  type: string | null;
  description: string | null;
  updated_at: string;
}

export interface DraftResponse {
  data: Draft;
}

export interface DraftCreateRequest {
  title?: string;
  type?: string;
  description?: string;
}

export interface DraftUpdateRequest {
  title?: string;
  type?: string;
  description?: string;
}

// ─── Notifications ────────────────────────────────────────────────────────────

export type NotificationType =
  | 'mention'
  | 'assignment'
  | 'state_change'
  | 'comment'
  | 'review_request'
  | 'system';

export interface Notification {
  id: string;
  type: NotificationType;
  actor_name: string | null;
  summary: string;
  deeplink: string | null;
  read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  data: Notification[];
}

// ─── Teams ────────────────────────────────────────────────────────────────────

export interface TeamMember {
  id: string;
  user_id: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  member_count: number;
  members: TeamMember[];
}

export interface TeamsResponse {
  data: Team[];
}

export interface TeamResponse {
  data: Team;
}

export interface TeamCreateRequest {
  name: string;
  description?: string;
}

export interface TeamAddMemberRequest {
  user_id: string;
}

// ─── Projects ─────────────────────────────────────────────────────────────────

export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface ProjectsResponse {
  data: Project[];
}

export interface ProjectResponse {
  data: Project;
}

export interface ProjectCreateRequest {
  name: string;
  description?: string;
}

// ─── Audit Events ─────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditEventsResponse {
  data: AuditEvent[];
  total: number;
}

// ─── Health ───────────────────────────────────────────────────────────────────

export type HealthStatus = 'ok' | 'degraded' | 'down';

export interface HealthCheck {
  name: string;
  status: HealthStatus;
  latency_ms: number | null;
  message: string | null;
}

export interface HealthResponse {
  status: HealthStatus;
  checks: HealthCheck[];
  version: string | null;
}

// ─── Tags ─────────────────────────────────────────────────────────────────────

export interface Tag {
  id: string;
  name: string;
  color: string | null;
  archived: boolean;
  created_at: string;
}

export interface TagsResponse {
  data: Tag[];
}

export interface TagResponse {
  data: Tag;
}

export interface TagCreateRequest {
  name: string;
  color?: string;
}

// ─── Integrations ─────────────────────────────────────────────────────────────

export interface IntegrationConfig {
  id: string;
  provider: string;
  enabled: boolean;
  config: Record<string, unknown>;
  created_at: string;
}

export interface IntegrationConfigsResponse {
  data: IntegrationConfig[];
}
