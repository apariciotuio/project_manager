export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  // Nullable pre-picker: a user with 0 active memberships has no workspace yet.
  workspace_id: string | null;
  workspace_slug: string | null;
  is_superadmin: boolean;
}

export interface AuthMeResponse {
  data: AuthUser;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.code = body.code;
    this.status = status;
    this.details = body.details;
  }
}

export class UnauthenticatedError extends Error {
  constructor() {
    super('Session expired — please log in again');
    this.name = 'UnauthenticatedError';
  }
}
