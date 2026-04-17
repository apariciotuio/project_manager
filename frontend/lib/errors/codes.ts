/**
 * TS mirror of backend/app/domain/errors/codes.py ERROR_CODES registry.
 *
 * MANUAL SYNC REQUIRED: when adding a new error code to the Python registry,
 * add the corresponding entry here. Both files must stay in sync.
 *
 * When the registry exceeds ~50 codes, consider codegen instead of manual sync.
 */

export type ErrorCode =
  | 'VALIDATION_ERROR'
  | 'INVALID_INPUT'
  | 'UNAUTHORIZED'
  | 'INVALID_CREDENTIALS'
  | 'FORBIDDEN'
  | 'NOT_FOUND'
  | 'TEAM_MEMBER_ALREADY_EXISTS'
  | 'TAG_NAME_TAKEN'
  | 'TAG_ARCHIVED'
  | 'PROJECT_NAME_TAKEN'
  | 'WORK_ITEM_INVALID_TRANSITION'
  | 'INTERNAL_ERROR'
  | 'UNKNOWN'; // synthetic — used for legacy { detail } responses

export const ERROR_CODE_STATUS: Record<ErrorCode, number> = {
  VALIDATION_ERROR: 400,
  INVALID_INPUT: 400,
  UNAUTHORIZED: 401,
  INVALID_CREDENTIALS: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  TEAM_MEMBER_ALREADY_EXISTS: 409,
  TAG_NAME_TAKEN: 409,
  TAG_ARCHIVED: 409,
  PROJECT_NAME_TAKEN: 409,
  WORK_ITEM_INVALID_TRANSITION: 422,
  INTERNAL_ERROR: 500,
  UNKNOWN: 0, // status comes from HTTP response, not this map
};
