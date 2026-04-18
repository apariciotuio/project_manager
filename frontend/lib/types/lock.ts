/**
 * EP-17 — Section lock domain types.
 *
 * Mirrors the backend SectionLock model. Endpoints:
 *   POST   /api/v1/sections/{id}/lock
 *   POST   /api/v1/sections/{id}/lock/heartbeat
 *   DELETE /api/v1/sections/{id}/lock
 *   POST   /api/v1/sections/{id}/lock/force-release
 *   GET    /api/v1/work-items/{id}/locks
 *   POST   /api/v1/sections/{id}/lock/unlock-request
 *   POST   /api/v1/sections/{id}/lock/respond
 */

/** Full lock payload returned by acquire / heartbeat. */
export interface SectionLockDTO {
  id: string;
  section_id: string;
  work_item_id: string;
  held_by: string;
  acquired_at: string; // ISO-8601
  heartbeat_at: string; // ISO-8601
  expires_at: string; // ISO-8601
}

/** Summary returned in list-locks response (may include display name). */
export interface SectionLockSummary {
  section_id: string;
  locked_by: string;
  locked_by_name: string | null;
  locked_at: string; // ISO-8601
}

/** Standard API envelope shapes */
export interface LockEnvelope {
  data: SectionLockDTO;
  message: string;
}

export interface LocksListEnvelope {
  data: SectionLockSummary[];
  message: string;
}

export interface LockReleaseEnvelope {
  data: { section_id: string };
  message: string;
}

/** Error codes the backend returns for lock conflicts */
export type LockErrorCode =
  | 'LOCK_CONFLICT'
  | 'LOCK_FORBIDDEN'
  | 'NOT_FOUND'
  | 'NO_ACTIVE_LOCK'
  | 'CANNOT_REQUEST_OWN_LOCK'
  | 'ALREADY_RESPONDED';

/** Shape of the 409 / 403 conflict detail */
export interface LockConflictDetail {
  error: {
    code: LockErrorCode;
    message: string;
    details: { held_by?: string };
  };
}

/** Unlock request — mirrors backend LockUnlockRequest.to_dict() */
export interface UnlockRequestDTO {
  id: string;
  section_id: string;
  requester_id: string;
  reason: string;
  created_at: string; // ISO-8601
  expires_at: string; // ISO-8601
  responded_at: string | null;
  response_action: 'accept' | 'decline' | null;
  response_note: string | null;
}

/** Envelope for unlock-request response */
export interface UnlockRequestEnvelope {
  data: UnlockRequestDTO;
  message: string;
}

/** Body for respond-to-request */
export interface RespondToRequestBody {
  request_id: string;
  action: 'accept' | 'decline';
  note?: string;
}
