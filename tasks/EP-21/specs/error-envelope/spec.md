# Spec — Descriptive Error Envelope (F-4)

**Capability:** Backend returns structured errors; frontend maps them to field-level UI.

## Scenarios

### Backend error envelope shape

- **WHEN** any controller raises `HTTPException` or Pydantic `ValidationError`
- **THEN** the response body is `{ "error": { "code": "<SNAKE_CASE>", "message": "<human-readable>", "field"?: "<field_name>", "details"?: {...} } }`
- **AND** the HTTP status code is preserved
- **AND** the `code` is a stable identifier from the central registry (`backend/app/domain/errors/codes.py`)

### Validation error maps to field

- **WHEN** a request body fails Pydantic validation on field `email`
- **THEN** the response is `400` with `{ error: { code: "VALIDATION_ERROR", message: "...", field: "email", details: { constraint: "email_format" } } }`

### Domain error preserves code

- **WHEN** `TeamMemberAlreadyExists` is raised from the service layer
- **THEN** the response is `409` with `code: "TEAM_MEMBER_ALREADY_EXISTS"` and a specific message
- **AND** `field: "user_id"` is set

### Invalid state transition

- **WHEN** a user attempts to transition a work item from `done` to `inbox`
- **THEN** the response is `422` with `code: "WORK_ITEM_INVALID_TRANSITION"` and `details: { from: "done", to: "inbox" }`

### Backward compatibility

- **WHEN** a consumer sends a request and the server returns a legacy `{ "detail": "..." }` shape (no refactor yet)
- **THEN** the frontend `apiClient` still parses it and throws `ApiError("UNKNOWN", detail)`
- **AND** no runtime crash occurs

### Frontend typed error

- **WHEN** the frontend receives a non-2xx response
- **THEN** `apiClient` throws `ApiError` with properties `code`, `message`, `field?`, `details?`, `status`
- **AND** callers can `instanceof ApiError` to branch

### Field-level UI mapping

- **WHEN** a form submission fails with `field: "email"`
- **THEN** the corresponding input shows an error state and the `message` below it
- **AND** focus moves to the first erroring field

### Non-field errors render as toast

- **WHEN** an error has no `field` property
- **THEN** a toast appears with `code: message` (e.g. `TEAM_MEMBER_ALREADY_EXISTS: User is already a member of this team`)
- **AND** the toast auto-dismisses after 6 seconds

### Secrets never leaked

- **WHEN** an exception contains internal details (SQL, stack trace, secrets)
- **THEN** the response `message` is a generic `"Internal server error"` with `code: "INTERNAL_ERROR"`
- **AND** the full exception is logged server-side with correlation ID

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Error message leaks DB schema or secrets | Exception middleware scrubs internal details in production; logs full trace server-side only |
| Error code catalog drifts between backend and frontend | Generate a TS enum from the Python registry OR maintain as shared constant file; add CI check |
| Toast spam on repeated errors | Deduplicate toasts by `(code, field)` within 3-second window |
| Attackers enumerate valid users via error messages | Auth errors return generic `INVALID_CREDENTIALS` regardless of whether email exists |

## Out of Scope

- i18n of error messages (English only in this pass)
- Error analytics / dashboard (EP-12 observability work)
- Retry-after headers for rate limiting (existing, untouched)
