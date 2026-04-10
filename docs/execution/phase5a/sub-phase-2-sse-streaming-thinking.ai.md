# Sub-Phase 2: SSE Streaming + Thinking State

**Goal:** linkedin-ai-production
**Phase:** 5a — Search UI (Frontend)
**Depends on:** SP-1 (scaffold, layout, search bar must exist)
**Estimated effort:** 1.5h
**Source plan steps:** 4, 5

---

## Objective

Build the core streaming infrastructure: SSE types, the `useStreamingSearch` hook (native fetch + ReadableStream), the Next.js API route that proxies to FastAPI, a temporary backend stub for development, and the thinking state component. After this sub-phase, submitting a search query streams results into the console and shows animated progress steps.

## Context

- **Frontend:** `<linkedout-fe>/`
- **Backend:** `./` — for the temporary stub endpoint
- **Design system:** `<linkedout-fe>/docs/design/linkedout-design-system.md`
- SSE consumption uses **native fetch + ReadableStream + TextDecoder** — NOT Vercel AI SDK
- Backend search endpoint doesn't exist yet (Phase 4). Create a stub in the test SSE router.
- `why_this_person` is NOT on the initial `result` event — it arrives as a separate `explanations` event after all results.

## Pre-Flight Checks

Before starting, verify:
- [ ] SP-1 complete: app runs at localhost:3000, search bar exists with URL-driven query
- [ ] Backend test SSE router exists at `src/shared/test_endpoints/sse_router.py`
- [ ] FastAPI backend runs at `http://localhost:8000`

## Files to Create/Modify

```
Frontend (<linkedout-fe>/):
├── src/
│   ├── types/
│   │   └── search.ts                    # ProfileResult, SearchEvent, SearchEventType
│   ├── hooks/
│   │   └── useStreamingSearch.ts         # SSE streaming hook
│   ├── app/
│   │   └── api/search/stream/route.ts    # Next.js SSE proxy route
│   └── components/
│       └── search/
│           └── ThinkingState.tsx          # Progress steps animation

Backend (./):
└── src/shared/test_endpoints/sse_router.py  # Add POST /api/test/search stub
```

---

## Step 1: Shared SSE Types (Plan Step 4, task 3)

Create `src/types/search.ts`:

```typescript
// Matches Phase 4 SearchResultItem exactly
interface ProfileResult {
  connection_id: string
  crawled_profile_id: string
  full_name: string
  headline: string | null
  current_position: string | null
  current_company_name: string | null
  location_city: string | null
  location_country: string | null
  linkedin_url: string | null
  public_identifier: string | null  // for profile image lookup
  affinity_score: number | null     // 0-100 scale
  dunbar_tier: string | null        // inner_circle | active | familiar | acquaintance
  similarity_score: number | null   // only for vector searches
  connected_at: string | null       // ISO date string
  has_enriched_data: boolean
  why_this_person?: string | null   // patched client-side from explanations event
}

type SearchEventType = 'thinking' | 'result' | 'explanations' | 'done' | 'error'

interface SearchEvent {
  type: SearchEventType
  message?: string           // for thinking + error events
  payload?: Record<string, unknown>
}
```

These types are the **shared contract** between Phase 4 (backend) and Phase 5a (frontend).

---

## Step 2: Backend Stub Endpoint (Plan Step 4, task 0)

**Temporary** — extend `src/shared/test_endpoints/sse_router.py` in the backend.

Add `POST /api/test/search` that:
- Accepts `{ query: string }` body
- Returns SSE events in the correct format:
  1. `thinking` event: `{"type": "thinking", "message": "Routing query..."}`
  2. `thinking` event: `{"type": "thinking", "message": "Querying profiles..."}`
  3. 5-10 `result` events with realistic `ProfileResult` data (mix of enriched and unenriched)
  4. `explanations` event: `{"type": "explanations", "payload": {"conn_id_1": "Former colleague at Acme Corp", ...}}`
  5. `done` event: `{"type": "done", "payload": {"total": N, "query_type": "natural_language"}}`
- 200ms delay between events to simulate streaming
- Use actual `CrawledProfileSchema` fields for realistic data
- Mark as temporary with `# TODO: Remove when Phase 4 search endpoint is ready`

---

## Step 3: Next.js SSE Proxy Route (Plan Step 4, task 1)

Create `src/app/api/search/stream/route.ts`:
- Receives POST with `{ query, tenant_id, bu_id, app_user_id }`
- Forwards to FastAPI `POST /tenants/{tenant_id}/bus/{bu_id}/search` (use stub endpoint during dev: `POST /api/test/search`)
- Streams SSE events back to client
- Response headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache, no-transform`, `X-Accel-Buffering: no`

---

## Step 4: Streaming Search Hook (Plan Step 4, task 2)

Create `src/hooks/useStreamingSearch.ts`:
- Uses native `fetch` + `ReadableStream` + `TextDecoder` to consume SSE
- **State:**
  - `results: ProfileResult[]` — accumulated results
  - `thinkingMessage: string | null` — current thinking step
  - `isStreaming: boolean` — stream in progress
  - `isComplete: boolean` — done event received
  - `error: string | null` — error message
  - `totalResults: number | null` — from done event
- `search(query: string)` — initiates stream
- `abort()` — closes stream via `AbortController`
- **Batching:** Accumulate incoming results in a `useRef` array. Flush to state on `requestAnimationFrame` cadence (~200ms batches) to prevent re-render cascades.
- Handle `explanations` event: patch `why_this_person` onto matching results by `connection_id`
- Wire TanStack Query caching: same query string within 5 minutes returns cached results

---

## Step 5: Thinking State Component (Plan Step 5)

Create `src/components/search/ThinkingState.tsx`:
- Three labeled steps: "Routing query...", "Querying profiles...", "Scoring by affinity..."
- Each step updates based on SSE `thinking` events (from `thinkingMessage`)
- Pulsing animated bar (Tailwind `animate-pulse`)
- Disappears once first result card renders (when `results.length > 0`)
- Never show a bare spinner — always label the step
- Style per design system

---

## Step 6: Wire Search Bar to Streaming Hook

Connect the SearchBar (from SP-1) to `useStreamingSearch`:
- When URL query param `?q=<query>` changes, call `search(query)`
- Show loading spinner in SearchBar during streaming
- Pass `results`, `isStreaming`, `isComplete`, `thinkingMessage` down to page components
- For now, render results as simple JSON/list (profile cards come in SP-3)

---

## Completion Criteria

- [ ] Submitting a search query → thinking events appear in UI
- [ ] Result events stream in progressively (visible as list or JSON)
- [ ] `explanations` event patches `why_this_person` onto results
- [ ] Done event fires with result count
- [ ] Cancelling mid-stream (abort) closes the connection
- [ ] Re-running same query within 5 min returns cached results
- [ ] ThinkingState shows labeled progress steps, disappears on first result
- [ ] No Vercel AI SDK — only native fetch + ReadableStream
