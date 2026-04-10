# Sub-Phase 5: Enrichment UI + Export

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** SP-3 (profile cards must exist), SP-4 (import context needed)
**Estimated effort:** 1h
**Source plan steps:** 11, 12

---

## Objective

Build the enrichment UI (per-profile and batch enrichment with client-side cost estimate) and the CSV/clipboard export functionality. These features augment the search results experience.

## Context

- **Frontend:** `<linkedout-fe>/`
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`
- **Enrichment cost:** Computed client-side using shared config constant `ENRICHMENT_COST_PER_PROFILE` (reconciliation item C4). No backend estimate endpoint needed.
- Enrichment integrates with unenriched profile cards (from SP-3)
- Export operates over the filtered/sorted result set (from SP-3)

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-3 complete: enriched and unenriched profile cards render in results list
- [ ] SP-4 complete: import UI exists (enrichment is contextually related)
- [ ] Unenriched `ProfileCardUnenriched.tsx` has "Enrich" button placeholder

## Files to Create

```
<linkedout-fe>/src/
├── components/
│   ├── enrichment/
│   │   ├── EnrichmentPanel.tsx          # Batch enrichment UI
│   │   └── EnrichmentProgress.tsx       # Enrichment job status
│   └── search/
│       └── ExportMenu.tsx               # CSV/clipboard export
├── hooks/
│   └── useEnrichment.ts                 # Enrichment trigger + polling hook
├── types/
│   └── enrichment.ts                    # EnrichmentEvent types
└── lib/
    └── constants.ts                     # ENRICHMENT_COST_PER_PROFILE
```

---

## Step 1: Enrichment Types + Constants

Create `src/types/enrichment.ts`:
```typescript
interface EnrichmentJob {
  id: string
  status: 'queued' | 'enriching' | 'extracting_data' | 'generating_embeddings' | 'complete' | 'failed'
  profile_ids: string[]
  profiles_completed: number
  profiles_total: number
  created_at: string
  completed_at: string | null
}
```

Create/update `src/lib/constants.ts`:
```typescript
export const ENRICHMENT_COST_PER_PROFILE = 0.05  // USD — adjust as needed
```

---

## Step 2: Enrichment Panel (Plan Step 11, task 1)

Create `src/components/enrichment/EnrichmentPanel.tsx`:

**Two modes:**
- **Per-profile:** Wire the "Enrich" button on `ProfileCardUnenriched` to trigger enrichment for a single profile
- **Batch:** Select multiple unenriched profiles → "Enrich Selected (N profiles)" button

**Before confirming:** Show cost estimate computed client-side:
- `cost = count × ENRICHMENT_COST_PER_PROFILE`
- Display: "Estimated cost: $X.XX for N profiles"
- Confirmation dialog before proceeding

**On confirm:** Call `POST /tenants/{tenant_id}/bus/{bu_id}/enrichment/enrich` with profile IDs

---

## Step 3: Enrichment Progress (Plan Step 11, task 2)

Create `src/components/enrichment/EnrichmentProgress.tsx`:
- Shows enrichment job status (polling via TanStack Query at 5s intervals)
- States: queued → enriching → extracting data → generating embeddings → complete
- Per-profile status within batch (progress bar)

Create `src/hooks/useEnrichment.ts`:
- Trigger enrichment: `POST /tenants/{tenant_id}/bus/{bu_id}/enrichment/enrich`
- Poll status: `GET /tenants/{tenant_id}/bus/{bu_id}/enrichment-events`
- TanStack Query polling at 5s intervals during active enrichment
- Stops polling when complete or failed

---

## Step 4: Post-Enrichment Update (Plan Step 11, task 3)

After enrichment completes:
- Refresh the profile card: swap unenriched card → full enriched card
- Toast notification: "5 profiles enriched successfully"
- Use TanStack Query cache invalidation to refresh search results

---

## Step 5: CSV/Clipboard Export (Plan Step 12)

Create `src/components/search/ExportMenu.tsx`:
- Button on results page: "Export" (dropdown)
- Options: "Download CSV", "Copy to Clipboard"
- CSV columns: Name, Headline, Company, Position, Location, LinkedIn URL, Affinity Score, Connection Date
- Exports currently filtered/sorted results (respects facets and sort from SP-3)
- CSV generation is entirely client-side (data already in memory, no backend call)
- "Copy to Clipboard" uses tab-separated values

---

## Completion Criteria

- [ ] Clicking Enrich on unenriched profile → cost estimate shown → confirm → enrichment starts
- [ ] Batch selection works (checkboxes on unenriched cards)
- [ ] Cost estimate computed client-side: `count × ENRICHMENT_COST_PER_PROFILE`
- [ ] Progress indicator shows per-profile status during enrichment
- [ ] After enrichment, profile card updates to full enriched view
- [ ] Toast notification on enrichment completion
- [ ] Export CSV downloads with correct columns
- [ ] Copy to clipboard works (tab-separated)
- [ ] Export respects current filters and sort
