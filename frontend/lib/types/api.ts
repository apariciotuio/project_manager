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

// ─── EP-10: Admin Members (enhanced) ─────────────────────────────────────────

export type MemberState = 'active' | 'invited' | 'suspended' | 'deleted';

export interface AdminMember {
  id: string;
  user_id: string;
  email: string;
  display_name: string;
  state: MemberState;
  role: string;
  capabilities: string[];
  context_labels: string[];
  joined_at: string;
}

export interface AdminMembersResponse {
  data: {
    items: AdminMember[];
    pagination: { cursor: string | null; has_next: boolean };
  };
  message: string;
}

export interface InviteMemberRequest {
  email: string;
  context_labels?: string[];
  team_ids?: string[];
  initial_capabilities?: string[];
}

export interface PatchMemberRequest {
  state?: MemberState;
  capabilities?: string[];
  context_labels?: string[];
}

// ─── EP-10: Validation Rules ──────────────────────────────────────────────────

export type RuleEnforcement = 'recommended' | 'required' | 'blocked_override';

export interface ValidationRule {
  id: string;
  workspace_id: string;
  project_id: string | null;
  work_item_type: string;
  validation_type: string;
  enforcement: RuleEnforcement;
  active: boolean;
  effective: boolean;
  superseded_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ValidationRulesResponse {
  data: ValidationRule[];
  message: string;
}

export interface CreateValidationRuleRequest {
  project_id?: string;
  work_item_type: string;
  validation_type: string;
  enforcement?: RuleEnforcement;
}

export interface PatchValidationRuleRequest {
  enforcement?: RuleEnforcement;
  active?: boolean;
}

// ─── EP-10: Jira Config ───────────────────────────────────────────────────────

export type JiraConfigState = 'active' | 'disabled' | 'error';

export interface JiraConfig {
  id: string;
  workspace_id: string;
  project_id: string | null;
  base_url: string;
  auth_type: string;
  state: JiraConfigState;
  last_health_check_status: string | null;
  last_health_check_at: string | null;
  created_at: string;
}

export interface JiraConfigsResponse {
  data: JiraConfig[];
  message: string;
}

export interface JiraConfigResponse {
  data: JiraConfig;
  message: string;
}

export interface CreateJiraConfigRequest {
  base_url: string;
  auth_type?: string;
  credentials: Record<string, string>;
  project_id?: string;
}

export interface JiraProjectMapping {
  id: string;
  jira_config_id: string;
  jira_project_key: string;
  local_project_id: string | null;
  type_mappings: Record<string, string> | null;
}

export interface JiraMappingsResponse {
  data: JiraProjectMapping[];
  message: string;
}

export type JiraTestResult = { status: 'ok' | 'auth_failure' | 'unreachable'; message?: string };

// ─── EP-10: Context Presets ───────────────────────────────────────────────────

export interface PresetSource {
  type: string;
  label: string;
  url?: string;
  description?: string;
}

export interface ContextPreset {
  id: string;
  workspace_id: string;
  name: string;
  description: string | null;
  sources: PresetSource[];
  created_at: string;
  updated_at: string;
}

export interface ContextPresetsResponse {
  data: ContextPreset[];
  message: string;
}

export interface ContextPresetResponse {
  data: ContextPreset;
  message: string;
}

export interface CreateContextPresetRequest {
  name: string;
  description?: string;
  sources?: PresetSource[];
}

export interface PatchContextPresetRequest {
  name?: string;
  description?: string;
  sources?: PresetSource[];
}

// ─── EP-10: Admin Dashboard ───────────────────────────────────────────────────

export interface AdminDashboard {
  member_count: number;
  project_count: number;
  integration_count: number;
  recent_audit_count: number;
  health: 'healthy' | 'degraded' | 'error';
  work_items_by_state: Record<string, number>;
  total_active: number;
}

export interface AdminDashboardResponse {
  data: AdminDashboard;
  message: string;
}

// ─── EP-10: Support Tools ─────────────────────────────────────────────────────

export interface OrphanedWorkItem {
  id: string;
  title: string;
  owner_id: string;
  owner_display: string;
  owner_state: MemberState;
  created_at: string;
}

export interface PendingInvitation {
  id: string;
  email: string;
  expires_at: string;
  expiring_soon: boolean;
}

export interface FailedExport {
  id: string;
  work_item_id: string;
  work_item_title: string;
  error_code: string;
  attempt_count: number;
  created_at: string;
}

export type ConfigBlockedReason = 'suspended_owner' | 'deleted_team_in_rule' | 'archived_project';

export interface ConfigBlockedWorkItem {
  id: string;
  title: string;
  blocking_reason: ConfigBlockedReason;
}

export interface SupportDataResponse {
  data: unknown[];
  message: string;
}
