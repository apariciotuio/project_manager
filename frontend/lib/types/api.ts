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
  data: {
    items: Notification[];
    total: number;
    page: number;
    page_size: number;
  };
}

// EP-08 — backend notification shape (state-based, with extra payload)
export type NotificationState = 'unread' | 'read' | 'actioned';

export interface QuickAction {
  action: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  payload_schema: Record<string, unknown>;
}

export interface NotificationV2 {
  id: string;
  workspace_id: string;
  recipient_id: string;
  type: string;
  state: NotificationState;
  actor_id: string | null;
  subject_type: 'work_item' | 'review' | 'block' | 'team';
  subject_id: string;
  deeplink: string;
  quick_action: QuickAction | null;
  extra: Record<string, unknown>;
  created_at: string;
  read_at: string | null;
  actioned_at: string | null;
}

export interface NotificationsV2Response {
  data: {
    items: NotificationV2[];
    total: number;
    page: number;
    page_size: number;
  };
}

export interface UnreadCountResponse {
  data: { count: number };
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

// ─── Workspace Members ────────────────────────────────────────────────────────

export interface WorkspaceMember {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: string;
}

export interface WorkspaceMembersResponse {
  data: WorkspaceMember[];
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

export interface ProjectUpdateRequest {
  name?: string;
  description?: string;
}

// ─── Audit Events ─────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  category: string;
  action: string;
  actor_id: string | null;
  actor_display: string | null;
  entity_type: string | null;
  entity_id: string | null;
  before_value: Record<string, unknown> | null;
  after_value: Record<string, unknown> | null;
  context: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditEventsResponse {
  data: {
    items: AuditEvent[];
    total: number;
    page: number;
    page_size: number;
  };
}

// ─── Health (workspace work item state summary) ───────────────────────────────

export interface WorkspaceHealthResponse {
  data: {
    workspace_id: string;
    work_items_by_state: Record<string, number>;
    total_active: number;
  };
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
  workspace_id: string;
  integration_type: string;
  project_id: string | null;
  mapping: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  created_by: string;
}

export interface IntegrationConfigsResponse {
  data: IntegrationConfig[];
}

export interface IntegrationConfigResponse {
  data: IntegrationConfig;
}

export interface IntegrationConfigCreateRequest {
  integration_type: string;
  encrypted_credentials: string;
  project_id?: string;
  mapping?: Record<string, unknown>;
}
