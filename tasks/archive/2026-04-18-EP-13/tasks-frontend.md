# Frontend Tasks: EP-13 — Puppet Integration (Search + Sync)

> **Follows EP-19 (Design System & Frontend Foundations)**. Top-bar search contributes results into `CommandPalette`. Adopt `StateBadge` for doc-source indexing status, `HumanError` code `upstream_unavailable` for Puppet outages (no silent fallback), `EmptyStateWithCTA` for no-results, semantic tokens, i18n `i18n/es/search.ts`. Snippet highlighting is generated on the platform (Puppet returns plain text) — shared sanitizer utility. See `tasks/extensions.md#EP-19`.

**Epic**: EP-13
**Date**: 2026-04-13 (rewritten 2026-04-14 per decisions #4/#9/#24/#28)
**Status**: In Progress

> **Scope (2026-04-14)**: Puppet is the sole search backend. No mode toggle (hybrid/keyword/semantic), no provenance badges, no fallback banner (Puppet outage → 503 not a partial result). Add: prefix type-ahead, saved searches UI. Below is rewritten — obsolete sections removed.

---

## API Contracts (Reference)

```typescript
// GET /api/v1/search?q=...&cursor=&limit=&state=&type=&team_id=&owner_id=&include_archived=
// No `mode`, no `scope` — Puppet is the only search backend; doc results flow through the same endpoint.
type SearchResult = {
  id: string
  entity_type: 'work_item' | 'section' | 'comment' | 'task' | 'doc'
  title: string
  type?: string           // work_item only
  state?: string          // work_item only
  score: number
  snippet: string
  workspace_id: string
}

type SearchResponse = {
  data: SearchResult[]
  pagination: { cursor: string | null; has_next: boolean }
  meta: {
    puppet_latency_ms: number
  }
}

// GET /api/v1/search/suggest?q=...
type SuggestResult = { id: string; title: string; type: string }
type SuggestResponse = { data: SuggestResult[] }

// /api/v1/saved-searches CRUD
type SavedSearch = { id: string; name: string; query: string; filters: Record<string, unknown>; created_at: string; updated_at: string }

// GET /api/v1/work-items/{id}/related-docs
type RelatedDoc = {
  doc_id: string
  title: string
  source_name: string
  snippet: string
  url: string
  score: number
}
type RelatedDocsResponse = { data: RelatedDoc[] }

// GET /api/v1/docs/{doc_id}/content
type DocContent = {
  doc_id: string
  title: string
  content_html: string    // sanitized HTML
  url: string
  source_name: string
  last_indexed_at: string
}

// POST /api/v1/admin/integrations/puppet
type PuppetConfigCreate = { base_url: string; api_key: string; workspace_id: string }
type PuppetConfig = { id: string; base_url: string; state: string; last_health_check_status: string; last_health_check_at: string; created_at: string }

// POST /api/v1/admin/documentation-sources
type DocSourceCreate = { workspace_id: string; name: string; source_type: 'github_repo' | 'url' | 'path'; url: string; is_public: boolean }
type DocSource = { id: string; name: string; source_type: string; url: string; is_public: boolean; status: string; last_indexed_at: string | null; item_count: number | null }
```

---

## Group 1: Search Bar + Type-Ahead (decision #24)

**Acceptance Criteria**
WHEN the user types ≥2 chars THEN `GET /api/v1/search/suggest?q=...` is called with 150ms debounce
WHEN the user submits (Enter or click) THEN `GET /api/v1/search?q=...&<filters>` is called and results render
WHEN Puppet returns 503 THEN a persistent banner shows "Search is temporarily unavailable" and results area is empty

- [x] **[RED]** Write test: `SearchBar` debounces suggest calls at 150ms — 10 tests in `__tests__/components/search/search-bar-suggest.test.tsx`
- [x] **[RED]** Write test: suggest dropdown renders ≤5 results, keyboard nav (↑/↓/Enter)
- [x] **[RED]** Write test: 503 response shows "Search unavailable" banner
- [x] **[GREEN]** Implement `components/search/SearchBar.tsx` with prefix suggestions — 150ms debounce, `data-testid="suggest-dropdown"`, ARIA listbox/option/activedescendant, Escape closes
- [ ] **[REFACTOR]** URL state: `useSearchParams` drives `q` and filters — no React state duplication

---

## Group 2: Search Results List

**Acceptance Criteria**
WHEN results render THEN each card shows title, type/state, snippet (HTML-safe), entity-type icon
WHEN results are loading THEN skeleton cards render (not a spinner)
WHEN `entity_type='doc'` THEN `DocResultCard` renders (external link + source)

- [x] **[RED]** Write test: `SearchResultCard` renders title, snippet (sanitized), state/type chips — 6 tests in `__tests__/components/search/search-result-card.test.tsx`
- [x] **[GREEN]** Implement `components/search/SearchResultCard.tsx` — sanitizer fixed to strip script textContent before extraction
- [x] **[RED]** Write test: `DocResultCard` renders `source_name` and external link icon — 5 tests in `__tests__/components/search/doc-result-card.test.tsx`
- [x] **[GREEN]** Implement `components/search/DocResultCard.tsx`
- [x] **[RED]** Write test: `SearchResults` renders `DocResultCard` for `entity_type='doc'`, `SearchResultCard` otherwise — 6 tests in `__tests__/components/search/search-results-list.test.tsx`
- [x] **[RED]** Write test: skeleton cards render when `isLoading=true`
- [x] **[GREEN]** Add skeleton loading state (3 placeholder cards) to `SearchResults.tsx`
- [x] **[REFACTOR]** Pagination: "Load more" button using cursor from `pagination`
- [x] Removed: `ProvenanceBadge`, `ModeToggle`, hybrid/keyword/semantic mode switcher, Puppet-fallback banner. Puppet is the only backend — no provenance to display (decision #4).

---

## Group 2b: Saved Searches (decision #24)

**Acceptance Criteria**
WHEN the user saves a search THEN `(name, query, filters)` is persisted for their user
WHEN the user opens the saved-search side panel THEN only their own saves are listed
WHEN the user clicks a saved search THEN the URL is replaced with the saved `(q, filters)` and results re-fetch

- [x] **[RED]** Write test: `SavedSearchesPanel` lists only the current user's saves — 8 tests in `__tests__/components/search/saved-searches-menu.test.tsx`
- [x] **[RED]** Write test: "Save this search" captures current URL query + filter state into a named save
- [x] **[RED]** Write test: rename + delete happy paths
- [x] **[GREEN]** Implement `components/search/SavedSearchesPanel.tsx` + API client in `lib/api/saved-searches.ts` — implemented as `saved-searches-menu.tsx` + `lib/api/saved-searches.ts` + `hooks/use-saved-searches.ts`

---

## Group 3: Doc Preview Panel

**Acceptance Criteria**
WHEN a doc result is clicked THEN a side panel slides in from the right
WHEN the panel is open THEN doc content renders as sanitized HTML
WHEN content is loading THEN a skeleton renders inside the panel
WHEN the user clicks "Open in new tab" THEN the original `url` opens in a new tab
WHEN the panel is closed THEN focus returns to the triggering element

- [x] **[RED]** Write component test: `DocPreviewPanel` is hidden by default
- [x] **[RED]** Write test: panel becomes visible when `isOpen=true`
- [x] **[RED]** Write test: panel calls `GET /api/v1/docs/{doc_id}/content` when opened
- [x] **[RED]** Write test: `content_html` is rendered inside the panel (dangerouslySetInnerHTML with sanitized content)
- [x] **[RED]** Write test: "Open in new tab" button has correct `href` and `target='_blank' rel='noopener noreferrer'`
- [x] **[RED]** Write test: close button / Escape key closes the panel — 8 tests in `__tests__/components/docs/doc-preview-panel.test.tsx`
- [x] **[GREEN]** Implement `components/docs/DocPreviewPanel.tsx`
  - Props: `docId: string | null`, `isOpen: boolean`, `onClose: () => void`
  - Slide-over from right, Tailwind transition
  - Fetches content via `useDocContent` hook on `docId` change
  - Renders `content_html` in sandboxed div (DOMParser sanitizer strips script/style/iframe/on* attrs)
  - Header: title, source_name, last_indexed_at, "Open in new tab" button
- [x] **[RED]** Write test: content_truncated flag shows "Content truncated" notice
- [x] **[GREEN]** Handle `content_truncated: true` in panel header
- [ ] **[REFACTOR]** Use `useQuery` with `staleTime: 3600_000` (matches server cache TTL) — currently uses module-level Map cache; functional equivalent, deferred to after React Query adoption

---

## Group 4: Related Docs Widget on Work Item Detail

**Acceptance Criteria**
WHEN a work item detail page loads THEN related docs load asynchronously (non-blocking)
WHEN Puppet is unavailable THEN the widget shows "No related docs available" (no error state visible)
WHEN a related doc is clicked THEN `DocPreviewPanel` opens

- [x] **[RED]** Write test: `RelatedDocsWidget` does NOT block the main detail render — renders heading immediately
- [x] **[RED]** Write test: widget calls `GET /api/v1/work-items/{id}/related-docs` after mount
- [x] **[RED]** Write test: up to 5 related docs render in the widget
- [x] **[RED]** Write test: on error/empty response, widget shows "No related docs available" text (not an error state) — 6 tests in `__tests__/components/docs/related-docs-widget.test.tsx`
- [x] **[RED]** Write test: clicking a doc opens `DocPreviewPanel` with correct `docId`
- [x] **[GREEN]** Implement `components/docs/RelatedDocsWidget.tsx`
  - Props: `workItemId: string`
  - Uses `useRelatedDocs` hook; `retry: false` (Puppet failure should not spam retries)
  - Renders compact list of related docs with title + snippet
- [x] **[GREEN]** Integrate `RelatedDocsWidget` into `WorkItemDetail.tsx` side panel area — added to spec tab right column in `app/workspace/[slug]/items/[id]/page.tsx`
- [x] **[GREEN]** Add `DocPreviewPanel` to `WorkItemDetail.tsx` with local open/close state — `previewDocId` state drives panel; placed at bottom of `PageContainer`
- [x] **[REFACTOR]** `RelatedDocsWidget` is lazy-loaded (`React.lazy` + `Suspense`) to keep detail page initial load fast — `Suspense` fallback `<Skeleton>`

---

## Group 5: Admin — Puppet Configuration Form

**Acceptance Criteria**
WHEN admin submits the config form THEN `POST /api/v1/admin/integrations/puppet` is called
WHEN the form has validation errors THEN inline errors are shown before submission
WHEN the config already exists THEN the form switches to edit mode (PATCH)
WHEN health check status is 'error' THEN a warning badge is shown

- [x] **[RED]** Write test: `PuppetConfigForm` renders base_url and api_key fields
- [x] **[RED]** Write test: empty base_url shows inline validation error
- [x] **[RED]** Write test: form submits POST with correct shape
- [x] **[RED]** Write test: existing config loads in edit mode (PATCH on submit)
- [x] **[RED]** Write test: health check status 'error' renders warning badge
- [x] **[RED]** Write test: "Test Connection" button calls `POST /api/v1/admin/puppet/{id}/health-check`
- [x] **[RED]** Write test: api_key field is masked (type=password) and not displayed after save — 10 tests in `__tests__/components/admin/puppet-config-form.test.tsx`
- [x] **[GREEN]** Implement `components/admin/PuppetConfigForm.tsx`
  - Controlled form (no react-hook-form, plain useState — simpler)
  - `api_key` field: password input, placeholder "Enter new key to rotate" when editing
  - "Test Connection" button: async, shows loading state, updates status after response
  - Health status badge: green=ok, red=error, gray=unchecked via `PuppetHealthBadge`
- [x] **[REFACTOR]** On successful save: invalidate `['puppet-config']` React Query cache — hooks use local state (no React Query); `onSaved` callback propagates updated config to `PuppetTab` state. Wired in admin page Puppet tab.

---

## Group 6: Admin — Documentation Sources CRUD UI

**Acceptance Criteria**
WHEN admin adds a doc source THEN the new source appears in the list with `status='pending'`
WHEN a source has `status='error'` THEN the error row is highlighted with error message
WHEN admin deletes a source THEN a confirmation dialog appears before deletion

- [x] **[RED]** Write test: `DocSourcesTable` renders list of sources with name, status, last_indexed_at columns
- [x] **[RED]** Write test: "Add Source" button opens `AddDocSourceModal`
- [x] **[RED]** Write test: `AddDocSourceModal` validates source_type-specific URL patterns
- [x] **[RED]** Write test: successful submit calls POST and closes modal
- [x] **[RED]** Write test: `status='error'` row shows error message in tooltip
- [x] **[RED]** Write test: delete button opens confirmation dialog
- [x] **[RED]** Write test: confirming delete calls DELETE endpoint and removes row from list — 9 tests in `__tests__/components/admin/doc-sources-table.test.tsx`, 11 tests in `__tests__/components/admin/add-doc-source-modal.test.tsx`
- [x] **[GREEN]** Implement `components/admin/DocSourcesTable.tsx`
  - Columns: Name, Type, URL (truncated), Public, Status (badge), Last Indexed, Actions
  - Status badges: pending=gray, indexing=blue, indexed=green, error=red
  - Delete: confirmation dialog
- [x] **[GREEN]** Implement `components/admin/AddDocSourceModal.tsx`
  - Fields: name, source_type (select), url, is_public (checkbox)
  - URL validation changes based on source_type (github_repo/url/path)
- [x] **[GREEN]** Wire both into admin page — new "Puppet" tab in `app/workspace/[slug]/admin/page.tsx` renders `PuppetConfigForm` + `DocSourcesTable` + `AddDocSourceModal`
- [x] **[REFACTOR]** Polling: sources with `status='pending'` or `status='indexing'` poll `GET /api/v1/admin/documentation-sources` every 5 seconds until stable — implemented in `hooks/use-doc-sources.ts` via setInterval

---

## i18n

- [x] Added `workspace.search.suggestions` + `workspace.search.unavailable` to `en.json` + `es.json`
- [x] Added `workspace.docs.*` namespace (`title`, `noRelatedDocs`, `previewDoc`, `previewTitle`, `openInNewTab`, `close`, `contentTruncated`, `loadError`) to both locales
- [x] Added `workspace.admin.integrations.puppet.*` namespace to both locales
- [x] Added `workspace.admin.docSources.*` namespace (columns, statusLabels, modal, delete dialogs) to both locales
