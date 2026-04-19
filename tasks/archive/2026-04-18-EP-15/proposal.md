# EP-15 — Tags + Labels

## Business Need

Users need to identify, group, and filter work items beyond the rigid taxonomy of `type` and `state`. Tags are lightweight, user-defined labels that can span projects and types. Examples:
- `needs-design`, `blocked-external`, `security-review`, `customer-request`
- Domain-specific: `motor`, `hogar`, `vida` (product lines)
- Process: `spike`, `tech-debt`, `compliance`

Without tags, users resort to putting markers in titles or descriptions — unsearchable and inconsistent.

## Objectives

- Support workspace-scoped tag catalog (admin-managed + user-created)
- Support attaching multiple tags to any work item
- Filter list views, dashboards, and search by tags (AND/OR logic)
- Tag autocomplete during creation (reuse existing tags, don't proliferate typos)
- Tag governance: admin can rename, merge, archive tags
- Color coding and optional icons for visual distinction

## User Stories

| ID | Story | Priority |
|---|---|---|
| US-150 | Create/edit/delete tags at workspace level | Must |
| US-151 | Attach/detach tags on a work item | Must |
| US-152 | Filter listings and dashboards by tags | Must |
| US-153 | Autocomplete tag input during editing | Must |
| US-154 | Admin: merge duplicate tags, rename, archive | Should |
| US-155 | Color code and icon per tag | Should |

## Acceptance Criteria

- WHEN a user adds a tag THEN it's stored in the workspace tag catalog if not already present
- WHEN a user types in tag input THEN autocomplete suggests existing tags (fuzzy match)
- WHEN filtering list by tags THEN supports both AND (all tags match) and OR (any tag matches) modes
- WHEN an admin archives a tag THEN it remains attached to existing items but doesn't appear in autocomplete or creation flows
- WHEN an admin merges tag A into tag B THEN all items with A get B, A is archived, operation is audited
- AND tag names are unique per workspace (case-insensitive)
- AND max 20 tags per work item (sanity limit)

## Technical Notes

- **New tables**:
  - `tags`: id, workspace_id, name, slug, color, icon, archived, created_by, created_at
  - `work_item_tags`: work_item_id, tag_id (composite PK)
- **Unique constraint**: `UNIQUE (workspace_id, LOWER(name))` WHERE NOT archived
- **Indexes**: `idx_work_item_tags_tag` for reverse lookup, `idx_tags_workspace_name_active` partial
- **Denormalized tag array**: consider `tag_ids UUID[]` on work_items for single-query filtering (vs join), maintained via triggers or service
- **API endpoints**:
  - `GET /api/v1/tags` — list workspace tags
  - `POST /api/v1/tags` — create (admin)
  - `PATCH /api/v1/tags/:id` — rename, archive, color
  - `POST /api/v1/tags/:id/merge-into/:target` — admin merge
  - `POST /api/v1/work-items/:id/tags` — attach
  - `DELETE /api/v1/work-items/:id/tags/:tag_id` — detach
- **Search integration**: filter param `?tags=a,b,c&tag_mode=and|or` on listings (EP-09)
- **Frontend**: Tag input with autocomplete (combobox), tag chips on item header, tag filter in list sidebar

## Dependencies

- EP-01 (work items)
- EP-09 (list filters + search)
- EP-10 (admin tag management)

## Complexity Assessment

**Medium** — Standard many-to-many with admin governance. Main complexity is tag search integration and autocomplete UX.

## Risks

- Tag proliferation if no governance (mitigated by admin merge/archive)
- Performance if many tags per item + many items (mitigated by indexes and optional denormalized array)
- Name collision / casing confusion (mitigated by LOWER unique constraint)
