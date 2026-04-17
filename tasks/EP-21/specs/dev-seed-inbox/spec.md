# Spec — Dev Seed Populates Inbox (F-2)

**Capability:** `seed_sample_data.py` creates notifications so EP-08 inbox is testable without manual events.

## Scenarios

### Seed creates inbox notifications

- **WHEN** `python backend/scripts/seed_sample_data.py` runs against an empty database
- **THEN** at least 10 rows exist in the `notifications` table for the seed user
- **AND** the notifications span the kinds `assigned`, `mentioned`, `review_requested`, `state_changed`

### At least 3 unread

- **WHEN** seed completes
- **THEN** at least 3 notifications have `read_at IS NULL`
- **AND** the unread count surfaces in the inbox page badge

### Idempotent re-run

- **WHEN** `seed_sample_data.py` runs a second time
- **THEN** notification count remains unchanged (no duplicates)
- **AND** no SQL integrity error is raised
- **AND** the script exits with code 0

### Chronological spread

- **WHEN** seed completes
- **THEN** notifications have `created_at` values spread across the last 14 days (not all clustered in the same second)
- **AND** at least one notification is within the last 24 hours

### Linked to real seed work items

- **WHEN** a notification is of kind `assigned` or `review_requested`
- **THEN** its `work_item_id` references an actual row seeded by the same script
- **AND** clicking the notification in the UI navigates to that work item

## Threat → Mitigation

| Threat | Mitigation |
|---|---|
| Seed runs against production and pollutes real user inbox | Existing guard: script aborts if `APP_ENV != "dev"` — reuse, do not bypass |
| Idempotency keyed on something flaky (timestamp) | Key on deterministic `(user_id, work_item_id, kind)` tuple; skip if exists |
| Notification table schema drifts | Wire the seed through the same repository used in production code, not raw SQL |

## Out of Scope

- Realtime WS dispatch of seeded notifications
- Seeding for multi-user workspaces (single seed user covers MVP)
