# Sub-Phase 4: Search History + Import UI

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** SP-1 (scaffold, layout shell must exist)
**Estimated effort:** 1.75h
**Source plan steps:** 9, 10

---

## Objective

Build the search history page (past searches, saved searches, query suggestions) and the import UI (CSV upload with drag-and-drop, source type selector, progress indicator, import history). These features are off the critical path and can run in parallel with SP-2 and SP-3.

## Context

- **Frontend:** `<linkedout-fe>/`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`
- Save search uses `PATCH /search-histories/{id}` with `{is_saved: true, saved_name: "..."}` (reconciliation item C6)
- Backend endpoints needed: search history CRUD, import endpoints (may need stubs)
- Query suggestions use `localStorage` for recent queries (keyed by tenant ID)

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-1 complete: app shell with navigation works, /history and /import pages exist as placeholders
- [ ] Design system spec read
- [ ] Check if backend search history and import endpoints exist; create stubs if needed

## Files to Create

```
<linkedout-fe>/src/
├── app/
│   ├── history/
│   │   └── page.tsx                     # Search history page (replace placeholder)
│   └── import/
│       └── page.tsx                     # Import UI page (replace placeholder)
├── components/
│   ├── search/
│   │   ├── SaveSearchDialog.tsx          # Save/name a search dialog
│   │   └── QuerySuggestions.tsx          # Autocomplete dropdown
│   └── import/
│       ├── FileUploadZone.tsx            # Drag-and-drop file upload
│       ├── ImportProgress.tsx            # Upload + processing progress
│       └── ImportHistory.tsx             # Past imports list
├── hooks/
│   ├── useSearchHistory.ts              # TanStack Query for history CRUD
│   └── useImportJob.ts                  # Import job polling hook
└── types/
    └── import.ts                        # ImportJob, ContactSource types
```

---

## Step 1: Search History Page (Plan Step 9, task 1)

Replace placeholder `src/app/history/page.tsx`:
- Paginated list of all past searches (from `search_history` backend entity)
- Each entry: query text, timestamp, result count
- Click → navigates to `/?q=<query>` to re-run the search
- TanStack Query for data fetching with pagination

Create `src/hooks/useSearchHistory.ts`:
- `GET /tenants/{tenant_id}/bus/{bu_id}/search-histories` — list, paginated
- TanStack Query with stale-while-revalidate

---

## Step 2: Save Search Dialog (Plan Step 9, task 2)

Create `src/components/search/SaveSearchDialog.tsx`:
- Button on results page: "Save Search"
- Dialog (shadcn/ui Dialog): name input field + save button
- Calls `PATCH /tenants/{tenant_id}/bus/{bu_id}/search-histories/{id}` with `{is_saved: true, saved_name: "..."}`
- Note: uses PATCH, not POST (reconciliation item C6)

---

## Step 3: Query Suggestions (Plan Step 9, task 3)

Create `src/components/search/QuerySuggestions.tsx`:
- Dropdown beneath search bar after 1+ chars typed
- Shows up to 5 recent queries from user's history
- 2-3 starter suggestions for first-time users (e.g., "engineers at YC startups", "product managers in SF")
- Local history via `localStorage` (keyed by tenant ID) for instant lookup — no backend call for suggestions
- Clicking a suggestion fills the search bar and submits

---

## Step 4: Import Types (Plan Step 10 setup)

Create `src/types/import.ts`:
```typescript
type ContactSource = 'linkedin_csv' | 'google_contacts' | 'icloud' | 'office'

interface ImportJob {
  id: string
  status: 'uploading' | 'processing' | 'deduplicating' | 'complete' | 'failed'
  source_type: ContactSource
  file_name: string
  total_rows: number | null
  new_connections: number | null
  duplicates_skipped: number | null
  matched_existing: number | null
  created_at: string
  completed_at: string | null
  error_message: string | null
}
```

---

## Step 5: Import Page + File Upload (Plan Step 10, tasks 1-3)

Replace placeholder `src/app/import/page.tsx`:
- File upload zone (drag-and-drop + click)
- Source type selector: LinkedIn CSV, Google Contacts, iCloud, Office
- Upload button triggers `POST /tenants/{tenant_id}/bus/{bu_id}/import` with file + source_type

Create `src/components/import/FileUploadZone.tsx`:
- shadcn/ui-styled file input with drag-and-drop
- File type validation (.csv, .vcf)
- File size display
- Visual feedback on drag-over

Create `src/components/import/ImportProgress.tsx`:
- Shows `ImportJob` status (polling via TanStack Query at 2s intervals)
- States: uploading → processing → deduplicating → complete
- Result summary: X new connections, Y duplicates skipped, Z matched to existing profiles
- Success illustration from design assets (if available)

Create `src/hooks/useImportJob.ts`:
- TanStack Query polling at 2s intervals during active import
- `GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs/{id}`
- Stops polling when status is 'complete' or 'failed'

---

## Step 6: Import History (Plan Step 10, task 4)

Create `src/components/import/ImportHistory.tsx`:
- List of past imports with date, source type, row count, status
- TanStack Query: `GET /tenants/{tenant_id}/bus/{bu_id}/import-jobs`

---

## Step 7: First-Time User State (Plan Step 10, task 5)

On the import page, if no connections exist:
- Show onboarding illustration + "Upload your LinkedIn connections to get started"
- Use illustration from design assets (if available), otherwise use a friendly empty state

---

## Completion Criteria

- [ ] History page lists past searches chronologically
- [ ] Clicking a past search re-runs it (navigates to /?q=...)
- [ ] Save search dialog saves a named search via PATCH
- [ ] Query suggestions appear as user types (from localStorage)
- [ ] CSV file uploads successfully to backend
- [ ] Import progress indicator updates during processing
- [ ] Re-uploading same file → zero new connections (dedup)
- [ ] Import history shows past uploads
- [ ] First-time user sees onboarding prompt
