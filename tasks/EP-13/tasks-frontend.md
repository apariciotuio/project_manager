# Frontend Tasks: EP-13 — Semantic Search + Puppet Integration

**Epic**: EP-13
**Date**: 2026-04-13
**Status**: Draft

---

## API Contracts (Reference)

```typescript
// POST /api/v1/search
type SearchRequest = {
  q: string
  mode: 'hybrid' | 'keyword' | 'semantic'
  scope: 'items' | 'docs' | 'all'
  limit?: number          // default 20, max 50
  cursor?: string | null
  include_archived?: boolean
}

type SearchResult = {
  id: string
  result_type: 'work_item' | 'doc'
  title: string
  type?: string           // work_item only
  state?: string          // work_item only
  score: number
  provenance: 'keyword' | 'semantic' | 'both'
  matched_by: Array<'keyword' | 'semantic'>
  snippet: string
  workspace_id: string
}

type SearchResponse = {
  data: SearchResult[]
  pagination: { cursor: string | null; has_next: boolean }
  meta: {
    total_count: number
    search_mode_used: 'hybrid' | 'keyword' | 'semantic'
    fallback_reason: 'puppet_unavailable' | null
  }
}

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

## Group 1: Search UI — Mode Toggle

**Acceptance Criteria**
WHEN the user clicks a mode tab THEN the URL param `mode` updates immediately
WHEN `mode` changes THEN the search query re-fires without losing the `q` value
WHEN Puppet fallback was used THEN a non-blocking info banner shows "Semantic search unavailable — showing keyword results"

- [ ] **[RED]** Write component test: `ModeToggle` renders three tabs (hybrid, keyword, semantic)
- [ ] **[RED]** Write test: clicking a tab updates `mode` URL param
- [ ] **[RED]** Write test: active tab reflects current `mode` URL param value
- [ ] **[GREEN]** Implement `components/search/ModeToggle.tsx`
  - Props: `mode: SearchMode`, `onChange: (mode: SearchMode) => void`
  - Renders as tab strip using Tailwind
- [ ] **[RED]** Write test: fallback banner renders when `meta.fallback_reason === 'puppet_unavailable'`
- [ ] **[GREEN]** Add fallback banner to `SearchResults.tsx` — reads from `meta`
- [ ] **[RED]** Write test: `SearchBar` passes `mode` in request body
- [ ] **[GREEN]** Update `SearchBar.tsx`: change from GET to POST `/api/v1/search`, include `mode` and `scope`
- [ ] **[REFACTOR]** URL state: `useSearchParams` drives `mode`, `scope`, `q` — no React state duplication

---

## Group 2: Search Results List with Provenance Badges

**Acceptance Criteria**
WHEN a result has `provenance='both'` THEN both "Keyword" and "Semantic" badges render
WHEN a result has `provenance='keyword'` THEN only "Keyword" badge renders
WHEN `result_type='doc'` THEN `DocResultCard` renders instead of work item card
WHEN results are loading THEN skeleton cards render (not a spinner)

- [ ] **[RED]** Write test: `ProvenanceBadge` renders "Keyword" for `provenance='keyword'`
- [ ] **[RED]** Write test: `ProvenanceBadge` renders both badges for `provenance='both'`
- [ ] **[GREEN]** Implement `components/search/ProvenanceBadge.tsx`
  - Props: `provenance: 'keyword' | 'semantic' | 'both'`
  - Keyword badge: blue; Semantic badge: violet; Both: both rendered
- [ ] **[RED]** Write test: `SearchResultCard` renders `ProvenanceBadge` using result.provenance
- [ ] **[GREEN]** Update `SearchResultCard.tsx`: add `ProvenanceBadge`, render snippet with highlight markup
- [ ] **[RED]** Write test: `DocResultCard` renders `source_name` and external link icon
- [ ] **[GREEN]** Implement `components/search/DocResultCard.tsx`
  - Shows title, source_name, snippet, provenance badge, external link to `url`
  - On click: opens `DocPreviewPanel` (not external URL directly)
- [ ] **[RED]** Write test: `SearchResults` renders `DocResultCard` for `result_type='doc'`, `SearchResultCard` for `work_item`
- [ ] **[GREEN]** Update `SearchResults.tsx`: type-dispatch on `result_type`
- [ ] **[RED]** Write test: skeleton cards render when `isLoading=true`
- [ ] **[GREEN]** Add skeleton loading state (3 placeholder cards) to `SearchResults.tsx`
- [ ] **[REFACTOR]** Pagination: "Load more" button using cursor from `meta.pagination`

---

## Group 3: Doc Preview Panel

**Acceptance Criteria**
WHEN a doc result is clicked THEN a side panel slides in from the right
WHEN the panel is open THEN doc content renders as sanitized HTML
WHEN content is loading THEN a skeleton renders inside the panel
WHEN the user clicks "Open in new tab" THEN the original `url` opens in a new tab
WHEN the panel is closed THEN focus returns to the triggering element

- [ ] **[RED]** Write component test: `DocPreviewPanel` is hidden by default
- [ ] **[RED]** Write test: panel becomes visible when `isOpen=true`
- [ ] **[RED]** Write test: panel calls `GET /api/v1/docs/{doc_id}/content` when opened
- [ ] **[RED]** Write test: `content_html` is rendered inside the panel (dangerouslySetInnerHTML with sanitized content)
- [ ] **[RED]** Write test: "Open in new tab" button has correct `href` and `target='_blank' rel='noopener noreferrer'`
- [ ] **[RED]** Write test: close button / Escape key closes the panel
- [ ] **[GREEN]** Implement `components/docs/DocPreviewPanel.tsx`
  - Props: `docId: string | null`, `isOpen: boolean`, `onClose: () => void`
  - Slide-over from right, Tailwind transition
  - Fetches content via React Query (`useQuery`) on `docId` change
  - Renders `content_html` in sandboxed div (CSP: no scripts)
  - Header: title, source_name, last_indexed_at, "Open in new tab" button
- [ ] **[RED]** Write test: content_truncated flag shows "Content truncated" notice
- [ ] **[GREEN]** Handle `content_truncated: true` in panel header
- [ ] **[REFACTOR]** Use `useQuery` with `staleTime: 3600_000` (matches server cache TTL)

---

## Group 4: Related Docs Widget on Work Item Detail

**Acceptance Criteria**
WHEN a work item detail page loads THEN related docs load asynchronously (non-blocking)
WHEN Puppet is unavailable THEN the widget shows "No related docs available" (no error state visible)
WHEN a related doc is clicked THEN `DocPreviewPanel` opens

- [ ] **[RED]** Write test: `RelatedDocsWidget` does NOT block the main detail render
- [ ] **[RED]** Write test: widget calls `GET /api/v1/work-items/{id}/related-docs` after mount
- [ ] **[RED]** Write test: up to 5 related docs render in the widget
- [ ] **[RED]** Write test: on error/empty response, widget shows "No related docs available" text (not an error state)
- [ ] **[RED]** Write test: clicking a doc opens `DocPreviewPanel` with correct `docId`
- [ ] **[GREEN]** Implement `components/docs/RelatedDocsWidget.tsx`
  - Props: `workItemId: string`
  - Uses `useQuery` with `enabled: !!workItemId`; `retry: false` (Puppet failure should not spam retries)
  - Renders compact list of related docs with title + snippet
- [ ] **[GREEN]** Integrate `RelatedDocsWidget` into `WorkItemDetail.tsx` side panel area
- [ ] **[GREEN]** Add `DocPreviewPanel` to `WorkItemDetail.tsx` with local open/close state
- [ ] **[REFACTOR]** `RelatedDocsWidget` is lazy-loaded (`React.lazy` + `Suspense`) to keep detail page initial load fast

---

## Group 5: Admin — Puppet Configuration Form

**Acceptance Criteria**
WHEN admin submits the config form THEN `POST /api/v1/admin/integrations/puppet` is called
WHEN the form has validation errors THEN inline errors are shown before submission
WHEN the config already exists THEN the form switches to edit mode (PATCH)
WHEN health check status is 'error' THEN a warning badge is shown

- [ ] **[RED]** Write test: `PuppetConfigForm` renders base_url and api_key fields
- [ ] **[RED]** Write test: empty base_url shows inline validation error
- [ ] **[RED]** Write test: form submits POST with correct shape
- [ ] **[RED]** Write test: existing config loads in edit mode (PATCH on submit)
- [ ] **[RED]** Write test: health check status 'error' renders warning badge
- [ ] **[RED]** Write test: "Test Connection" button calls `POST /api/v1/admin/puppet/{id}/health-check`
- [ ] **[RED]** Write test: api_key field is masked (type=password) and not displayed after save
- [ ] **[GREEN]** Implement `components/admin/PuppetConfigForm.tsx`
  - Controlled form with react-hook-form + zod validation
  - `api_key` field: password input, placeholder "Enter new key to rotate" when editing
  - "Test Connection" button: async, shows loading state, updates status after response
  - Health status badge: green=ok, red=error, gray=unchecked
- [ ] **[REFACTOR]** On successful save: invalidate `['puppet-config']` React Query cache

---

## Group 6: Admin — Documentation Sources CRUD UI

**Acceptance Criteria**
WHEN admin adds a doc source THEN the new source appears in the list with `status='pending'`
WHEN a source has `status='error'` THEN the error row is highlighted with error message
WHEN admin deletes a source THEN a confirmation dialog appears before deletion

- [ ] **[RED]** Write test: `DocSourcesTable` renders list of sources with name, status, last_indexed_at columns
- [ ] **[RED]** Write test: "Add Source" button opens `AddDocSourceModal`
- [ ] **[RED]** Write test: `AddDocSourceModal` validates source_type-specific URL patterns
- [ ] **[RED]** Write test: successful submit calls POST and closes modal
- [ ] **[RED]** Write test: `status='error'` row shows error message in tooltip
- [ ] **[RED]** Write test: delete button opens confirmation dialog
- [ ] **[RED]** Write test: confirming delete calls DELETE endpoint and removes row from list
- [ ] **[GREEN]** Implement `components/admin/DocSourcesTable.tsx`
  - Columns: Name, Type, URL (truncated), Public, Status (badge), Last Indexed, Actions
  - Status badges: pending=gray, indexing=blue spinner, indexed=green, error=red
  - Delete: confirmation dialog with "This will remove the source from search" message
- [ ] **[GREEN]** Implement `components/admin/AddDocSourceModal.tsx`
  - Fields: name, source_type (select), url, is_public (toggle)
  - URL validation changes based on source_type
- [ ] **[GREEN]** Wire both into admin integrations page (`app/admin/integrations/puppet/page.tsx`)
- [ ] **[REFACTOR]** Polling: sources with `status='pending'` or `status='indexing'` poll `GET /api/v1/admin/documentation-sources` every 5 seconds until stable (React Query `refetchInterval`)
