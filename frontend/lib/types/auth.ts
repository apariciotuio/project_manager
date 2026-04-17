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
  field?: string;
  details?: unknown;
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly field: string | undefined;
  readonly details: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.code = body.code;
    this.status = status;
    this.field = body.field;
    this.details = body.details;
  }

  static fromResponse(response: Response, body: unknown): ApiError {
    const status = response.status;

    if (body !== null && typeof body === 'object') {
      const b = body as Record<string, unknown>;

      // New envelope: { error: { code, message, field?, details? } }
      if (b['error'] !== null && typeof b['error'] === 'object') {
        const envelope = b['error'] as Record<string, unknown>;
        if (typeof envelope['code'] === 'string') {
          return new ApiError(status, {
            code: envelope['code'],
            message: typeof envelope['message'] === 'string' ? envelope['message'] : response.statusText || `HTTP ${status}`,
            field: typeof envelope['field'] === 'string' ? envelope['field'] : undefined,
            details: envelope['details'],
          });
        }
      }

      // Legacy shape: { detail: "..." }
      if (typeof b['detail'] === 'string') {
        return new ApiError(status, {
          code: 'UNKNOWN',
          message: b['detail'],
        });
      }
    }

    // Malformed / empty body fallback
    return new ApiError(status, {
      code: 'UNKNOWN',
      message: response.statusText || `HTTP ${status}`,
    });
  }
}

export class UnauthenticatedError extends Error {
  constructor() {
    super('Tu sesión ha caducado. Inicia sesión de nuevo.');
    this.name = 'UnauthenticatedError';
  }
}

export function isSessionExpired(err: unknown): boolean {
  return err instanceof UnauthenticatedError;
}
