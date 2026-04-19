# Spec: Tag Autocomplete Input — US-153

## Scope

Real-time tag suggestion as user types, filtered to active tags, with inline tag creation if user has capability.

---

## Scenario: Autocomplete with partial input

WHEN a user types 2 or more characters into a tag input field
THEN a request is sent to `GET /api/v1/tags?q=<query>&limit=10`
AND the response returns tags whose `name` contains the query string (case-insensitive substring match)
AND archived tags are excluded from results
AND results are ordered by: exact match first, then prefix match, then substring match, then alphabetical
AND the response returns at most 10 results

### Scenario: Autocomplete with 1 character

WHEN a user types exactly 1 character
THEN no request is sent (debounce threshold: 2 characters)
AND no suggestion list is shown

### Scenario: Autocomplete with empty input

WHEN the input field is focused with no text
THEN a request is sent to `GET /api/v1/tags?limit=10` (no `q` param)
AND the response returns the 10 most recently used tags in the workspace, ordered by usage recency
AND archived tags are excluded

### Scenario: No matching tags found

WHEN the query matches no active tags
AND the user does NOT have `capability=tags:write`
THEN the suggestion list shows "No tags found" and no creation option

WHEN the query matches no active tags
AND the user HAS `capability=tags:write`
THEN the suggestion list shows a "Create tag '<query>'" option as the last item

### Scenario: Create tag on-the-fly from autocomplete

WHEN a user selects the "Create tag '<query>'" option
THEN a `POST /api/v1/tags` request is made with `{ name: <query> }`
AND if creation succeeds, the new tag is immediately attached to the current work item
AND the new tag appears in the tag list on the work item
AND the new tag is added to the workspace tag catalog

WHEN the `POST /api/v1/tags` request fails with `409 Conflict` (slug conflict)
THEN the UI shows an inline error "A tag with this name already exists"
AND the existing conflicting tag is surfaced in the suggestion list

### Scenario: Selecting an existing tag from autocomplete

WHEN a user clicks or presses Enter on a suggestion
THEN the tag is attached to the current work item via `POST /api/v1/work-items/:id/tags`
AND the suggestion list closes
AND the selected tag appears as a chip in the work item's tag area

### Scenario: Attaching an already-attached tag from autocomplete

WHEN a user selects a tag that is already attached to the current work item
THEN the tag appears visually de-emphasized (dimmed) in the suggestion list
AND selecting it is a no-op (no API call)
AND the suggestion list closes without error

### Scenario: Debounce behavior

WHEN a user types rapidly
THEN requests are debounced with a 200ms delay after the last keystroke
AND only the latest request's response is used (previous in-flight requests are cancelled/ignored)

### Scenario: Workspace scoping

WHEN the autocomplete returns results
THEN only tags belonging to the current workspace are returned
AND cross-workspace tag leakage is not possible

---

## Non-Functional

- API endpoint: `GET /api/v1/tags?q=<query>&limit=<n>&archived=false`
- `archived=false` is the default; clients do not need to pass it explicitly
- Fuzzy match implementation: case-insensitive `ILIKE '%query%'` on `name` column, backed by `pg_trgm` trigram index for performance at scale
- Debounce: 200ms client-side, no server-side rate limit beyond standard workspace API rate limits
- Max response time for autocomplete: 100ms p95 (small dataset, indexed)
- The `capability=tags:write` check for on-the-fly creation is enforced server-side; the UI hint is a convenience only
