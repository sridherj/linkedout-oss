---
feature: search-conversation-flow
module: extension/entrypoints/sidepanel, extension/lib/backend/search, backend/src/linkedout/intelligence/controllers
linked_files:
  - extension/entrypoints/sidepanel/App.tsx
  - extension/entrypoints/sidepanel/components/BestHopPanel.tsx
  - extension/lib/backend/search.ts
  - extension/lib/backend/types.ts
  - extension/lib/messages.ts
  - backend/src/linkedout/intelligence/controllers/search_controller.py
  - backend/src/linkedout/intelligence/controllers/best_hop_controller.py
  - backend/src/linkedout/intelligence/controllers/_sse_helpers.py
  - backend/src/linkedout/intelligence/contracts.py
parent_spec: docs/specs/search_sessions.collab.md
version: 1
last_verified: "2026-04-09"
---

# Search Conversation Flow — Extension + Backend SSE

**Created:** 2026-04-09
**Status:** Implemented (Best Hop only; general search UI not yet built)

## Intent

Define how search conversations flow between the Chrome extension sidepanel and the backend SSE endpoints. In LinkedOut OSS, the search UI lives in the Chrome extension sidepanel (not a standalone React app). The extension currently implements **Best Hop search** (find introduction paths via mutual connections). The backend also exposes a general-purpose **SSE streaming search endpoint** (`POST /search`) with session/turn persistence, but no extension UI consumes it yet.

This spec documents what is implemented today and the SSE contract that a future search UI would consume.

## Architecture Overview

```
Chrome Extension                    Backend
┌─────────────────┐         ┌──────────────────────┐
│ BestHopPanel     │         │ best_hop_controller   │
│ (sidepanel UI)   │◄──msg──►│ POST /best-hop (SSE)  │
│                  │         │                      │
│ [Future: search  │         │ search_controller     │
│  conversation UI]│         │ POST /search (SSE)    │
└─────────────────┘         │ GET /search/similar   │
        ▲                    │ GET /search/intros    │
        │ chrome.runtime     │ GET /search/profile   │
        │ messages           └──────────────────────┘
        ▼
┌─────────────────┐
│ Service Worker   │
│ (orchestrator)   │
│ streamBestHop()  │
└─────────────────┘
```

Communication uses Chrome extension messaging (sidepanel <-> service worker) with the service worker making SSE fetch calls to the backend.

## Best Hop Flow (Implemented)

### State Machine

BestHopPanel has five phases managed by local `useState`:

| Phase | Meaning | UI |
|-------|---------|-----|
| `idle` | No search in progress | "Find intro path" trigger card |
| `extracting` | Scraping mutual connections from LinkedIn | Progress bar with page count, speed control (1x/2x/4x/8x), cancel button |
| `analyzing` | SSE stream in progress from backend | Thinking message, progress bar, cancel button |
| `done` | Results received | Result cards with rank, name, role, affinity score, reasoning; "New search" button |
| `error` | Failure during extraction or search | Error banner with message, retry button |

### Message Flow

**Phase 1 — Trigger (sidepanel -> service worker):**
1. User clicks "Find intro path" on BestHopPanel
2. Panel sends `FIND_BEST_HOP` message with `entityUrn`, `linkedinUrl`, `profileName`
3. Panel sets phase to `extracting`, resets all state

**Phase 2 — Extraction (service worker -> content script -> sidepanel):**
1. Service worker sends `EXTRACT_MUTUAL_CONNECTIONS` to content script
2. Content script scrapes LinkedIn mutual connections pages
3. Service worker relays `MUTUAL_EXTRACTION_PROGRESS` messages (page count, total) to sidepanel
4. Content script sends `MUTUAL_CONNECTIONS_READY` with extracted URLs back to service worker

**Phase 3 — SSE Search (service worker -> backend -> sidepanel):**
1. Service worker calls `streamBestHop()` from `extension/lib/backend/search.ts`
2. `streamBestHop()` POSTs to `POST /tenants/{tenant_id}/bus/{bu_id}/best-hop` with `Accept: text/event-stream`
3. Backend streams SSE events; service worker parses and relays as Chrome extension messages

### SSE Event Mapping (Best Hop)

| Backend SSE Event | Extension Message | BestHopPanel State Change |
|-------------------|-------------------|---------------------------|
| `thinking` | `BEST_HOP_THINKING` | `phase = 'analyzing'`, update `thinkingMessage` |
| `result` | `BEST_HOP_RESULT` | Append to `results[]` (rank, name, role, affinityScore, reasoning, linkedinUrl) |
| `done` | `BEST_HOP_COMPLETE` | `phase = 'done'`, set `matchedCount`, `unmatchedCount` |
| `error` | `BEST_HOP_ERROR` | `phase = 'error'`, set `errorMessage` with phase (`extraction` or `search`) |
| `session` | (ignored) | Not relevant for Best Hop display |
| `conversation_state` | (ignored) | Not relevant for Best Hop display |
| `explanations` | (ignored) | Not consumed; could be merged in future |
| `heartbeat` | (ignored) | Keeps connection alive (15s interval) |

### SSE Parsing

`streamBestHop()` in `extension/lib/backend/search.ts` handles the raw SSE stream:
- Reads response body via `ReadableStream` with `TextDecoder`
- Buffers incomplete lines across chunks
- Parses `data: <json>` lines, skips `data: [DONE]`
- Tracks `resultRank` incrementally (backend results don't carry rank)
- Calls `onEvent()` callback for each parsed event
- Handles `AbortError` silently (user cancelled)

### Cancellation

- User clicks "Cancel" -> panel sends `CANCEL_BEST_HOP` to service worker
- Service worker aborts the in-flight fetch (via `AbortController`)
- Panel sets `phase = 'done'` immediately (shows partial results if any)

### Speed Control

- Panel renders a speed chip (1x/2x/4x/8x) during extraction phase
- Click cycles through: 1 -> 2 -> 4 -> 8 -> 1
- Sends `SET_EXTRACTION_SPEED` message to service worker
- Service worker may auto-downshift on 429 errors, sending `EXTRACTION_SPEED_CHANGED` back

### Error Handling

- Network unreachable: `streamBestHop()` catches fetch error, emits `{type: 'error', data: {message: 'Backend is unreachable'}}`
- HTTP error: reads response body, emits error with `{status}: {body || statusText}`
- Stream read failure: catches non-abort errors, emits error with message
- All errors propagate as `BEST_HOP_ERROR` with `phase: 'extraction' | 'search'`

## Backend SSE Search Endpoint (Available, No Extension UI)

The backend exposes `POST /tenants/{tenant_id}/bus/{bu_id}/search` for general-purpose conversational search. This endpoint streams the same SSE protocol but with richer events.

### SSE Events (General Search)

| SSE Event | Payload | Purpose |
|-----------|---------|---------|
| `thinking` | `{message}` | Status updates ("Starting search...", "Generating explanations...") |
| `session` | `{session_id}` | Emitted once on new session creation |
| `result` | `SearchResultItem` | Individual result (streamed one at a time, not batched) |
| `explanations` | `{connection_id: ProfileExplanation}` | Batched "Why This Person" explanations (batch size from `WhyThisPersonExplainer.BATCH_SIZE`) |
| `conversation_state` | `{result_summary_chips, suggested_actions, result_metadata, facets}` | Structured metadata for conversation thread rendering |
| `done` | `{total, query_type, answer, session_id}` | Stream complete; includes natural language answer |
| `error` | `{message}` | Stream-level error |
| `heartbeat` | `{}` | Keep-alive every 15 seconds |

### Session Lifecycle

1. Client sends `POST /search` with `{query, session_id?, limit?}`
2. If `session_id` is null: backend creates new `SearchSession`, returns `session_id` via `session` event
3. If `session_id` is provided: backend loads existing session + turn history for context continuity
4. After results stream, backend persists a `SearchTurn` row with results, transcript, and summary
5. Session `turn_count` and `last_active_at` are updated

### Additional Search Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /search/similar/{connection_id}` | POST | Vector similarity search (no LLM, pure embedding distance) |
| `GET /search/intros/{connection_id}` | GET | Warm intro paths via shared company connections |
| `GET /search/profile/{connection_id}` | GET | Full profile detail for slide-over panel (4 tabs: overview, experience, affinity, ask) |

## Component Responsibilities

### `BestHopPanel` (extension sidepanel component)

Owns: `phase`, `results[]`, `matchedCount`, `unmatchedCount`, `errorMessage`, `errorPhase`, `speed`, `thinkingMessage`, `extractionPage`, `extractionTotal`.

Renders inline within the profile tab of the sidepanel (below ProfileCard, RateLimitBar, and FetchButton). Not a separate page or route.

Listens for Chrome extension messages via `browser.runtime.onMessage`.

### `streamBestHop()` (extension lib — SSE client)

Runs in service worker context. Owns the SSE fetch lifecycle:
- Constructs URL from config (`backendUrl`, `tenantId`, `buId`)
- Sets `X-App-User-Id` header from config
- Normalizes LinkedIn URLs before sending
- Parses SSE stream and calls `onEvent()` callback
- Respects `AbortSignal` for cancellation

### `App.tsx` (extension sidepanel root)

Owns: `activeTab` (`profile` | `activity`), `profileData`, `badgeStatus`, `rateLimits`, `isFetching`, `isOnProfile`, `enrichmentMode`, `banner`, `logEntries`, `unreadCount`, `isOffline`, `challengeActive`.

Renders BestHopPanel only when a profile is loaded and visible. BestHopPanel is disabled when `entityUrn` is null.

### Backend Controllers

- `search_controller.py`: `search_router` with 4 endpoints (SSE search, similar, intros, profile detail)
- `best_hop_controller.py`: `best_hop_router` with 1 SSE endpoint
- `_sse_helpers.py`: Shared utilities (`sse_line`, `stream_with_heartbeat`, `create_or_resume_session`, `save_session_state`)

## Decisions

| Decision | Chose | Over | Because |
|----------|-------|------|---------|
| Search UI location | Chrome extension sidepanel | Standalone React app (linkedout-fe) | OSS ships as extension + backend; no separate web frontend |
| Best Hop first | Implement Best Hop before general search | General conversational search UI | Best Hop is the primary extension use case (you're already on a LinkedIn profile) |
| SSE via service worker | Service worker makes SSE fetch, relays via Chrome messages | Sidepanel makes SSE fetch directly | Service worker can run in background, survives sidepanel close, coordinates with content scripts |
| Individual result events | Stream each result as separate `result` event | Batch all results in single `results` event | Backend sends results individually; extension accumulates them progressively |
| Phase-based state | Simple `phase` string enum in BestHopPanel | Full state machine hook (like useStreamingSearch) | Best Hop has a linear flow (idle -> extracting -> analyzing -> done); no need for complex state management |
| No session UI | Backend persists sessions but extension doesn't expose session history | Session switcher / resume UI | Extension is contextual to current LinkedIn profile; session resume is a future feature |

## Not Included

- **General search conversation UI in extension** — backend SSE endpoint exists but no extension component consumes `POST /search` for free-text queries with conversation thread, follow-up bar, or session resume
- **Session switcher / resume** — backend supports session persistence and turn history but the extension has no UI to browse or resume past sessions
- **Facet filtering** — backend sends `facets` in `conversation_state` but no client-side facet panel exists
- **Explanation rendering** — `explanations` SSE events are ignored by BestHopPanel; no UI for "Why This Person" cards
- **Split-panel layout** — no results panel + chat panel split; BestHopPanel renders inline
- **Client-side result caching** — no TanStack Query or equivalent; results live in component state only
- **Streaming progress indicator** (% complete)
