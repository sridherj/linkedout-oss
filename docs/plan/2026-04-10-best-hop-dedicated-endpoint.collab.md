# Best Hop: Dedicated Endpoint Design

## Context

The "Find Best Hop" feature currently sends a natural language query through the generic `/search` endpoint. The search agent takes **7 iterations / ~42s** doing redundant discovery work — web searches, iterative SQL, 12 profile lookups — when the extension already has the structured data (target + mutual connection URLs).

## Core Insight: Two-Hop Ranking

Best hop is a **two-hop** problem. For each mutual connection M:
- **Leg 1 (User → M)**: How close am I to this person? → Pre-computed `affinity_score`
- **Leg 2 (M → Target)**: How close is M to the target? → Inferred from work experience overlap, shared companies, seniority proximity, location, etc.

The LLM should rank by synthesizing **both legs**, not just affinity.

## Design: `POST /best-hop` Endpoint

### Principle: Trust the LLM

The current problem isn't that the LLM is in the loop — it's that the LLM starts blind and wastes 7 iterations discovering what it needs. The fix: **give it a running start** with pre-assembled context, plus tools if it needs to dig deeper.

### Request

```python
class BestHopRequest(BaseModel):
    target_name: str                    # "Chandra Sekhar Kopparthi"
    target_url: str                     # "https://linkedin.com/in/chandrasekharkopparthi"
    mutual_urls: list[str]              # LinkedIn URLs from mutual connections page
    session_id: Optional[str] = None    # Resume existing session (future)
```

Target profile is always enriched in DB (extension enriches on visit, before best-hop triggers). Target may or may not be a 1st-degree connection.

### Response: SSE Stream

Same event types as existing search — extension parsing unchanged.

```
data: {"type": "session", "payload": {"session_id": "ss_xxx"}}
data: {"type": "thinking", "message": "Found 18 of 24 mutual connections in your network..."}
data: {"type": "result", "payload": {rank, connection_id, crawled_profile_id, full_name, current_position, current_company_name, affinity_score, dunbar_tier, linkedin_url, why_this_person}}
data: {"type": "result", "payload": {...}}
...
data: {"type": "done", "payload": {"total": 8, "matched": 18, "unmatched": 6, "session_id": "ss_xxx"}}
```

### Pipeline

#### Step 1: Pre-assemble Context (~100ms)

Batch lookup the structured data the LLM needs, so it doesn't have to discover it via tool calls.

**Query 1 — Mutual connections:**
```sql
SELECT cp.id, cp.full_name, cp.headline, cp.current_position,
       cp.current_company_name, cp.linkedin_url, cp.location_city,
       cp.seniority_level, cp.about,
       c.id AS connection_id, c.affinity_score, c.dunbar_tier,
       c.affinity_career_overlap, c.affinity_external_contact,
       c.affinity_recency, c.connected_at
FROM crawled_profile cp
JOIN connection c ON c.crawled_profile_id = cp.id
WHERE cp.linkedin_url = ANY(:mutual_urls)
ORDER BY c.affinity_score DESC NULLS LAST
```

**Query 2 — Experience history for top 50 mutuals (by affinity):**
```sql
SELECT e.crawled_profile_id, e.company_name, e.company_id, e.position,
       e.start_date, e.end_date, e.is_current, e.seniority_level
FROM experience e
WHERE e.crawled_profile_id = ANY(:top_50_profile_ids)
ORDER BY e.crawled_profile_id, e.start_date DESC
```

**Query 3 — Target profile:**
```sql
SELECT cp.id, cp.full_name, cp.headline, cp.current_position, cp.current_company_name,
       cp.location_city, cp.seniority_level, cp.about
FROM crawled_profile cp
WHERE cp.linkedin_url = :target_url
LIMIT 1
```

**Query 4 — Target's experience:**
```sql
SELECT e.company_name, e.company_id, e.position, e.start_date, e.end_date,
       e.is_current, e.seniority_level
FROM experience e
WHERE e.crawled_profile_id = :target_profile_id
ORDER BY e.start_date DESC
```

Also check if target is a direct connection (for LLM context):
```sql
SELECT c.affinity_score, c.dunbar_tier
FROM connection c WHERE c.crawled_profile_id = :target_profile_id
LIMIT 1
```

All queries ~100ms total. RLS scopes connection queries to current user.

Track matched vs unmatched mutual URLs for the `done` event.

#### Step 2: LLM Ranking (single call, streamed, ~5-8s)

Inject pre-assembled context into the system prompt: target profile + experience, each mutual's profile + experience + affinity data. The LLM starts with everything it needs to rank and generate reasoning.

**Optional tools available** (same as search agent, for edge cases):
- `get_profile_detail` — if LLM wants deeper data on a specific candidate
- `execute_sql` — if LLM needs something not in the pre-assembled context

In practice, the LLM should complete in **1-2 iterations** (likely just 1 — final answer with ranked results). The tools are a safety net, not the expected path.

**Output**: Up to 30 ranked results, streamed per-candidate as SSE `result` events. Each includes `why_this_person` reasoning.

**Model**: Uses `SEARCH_LLM_MODEL` config (same as search agent).

#### Step 2.5: Merge SQL + LLM Data

LLM returns `{crawled_profile_id, rank, why_this_person}` per candidate. Service builds a lookup dict from Query 1 results keyed by `crawled_profile_id`, enriches each LLM result with SQL-sourced fields (`connection_id`, `full_name`, `current_position`, `current_company_name`, `affinity_score`, `dunbar_tier`, `linkedin_url`) before emitting SSE events.

#### Step 3: Persist Session (fire-and-forget)

Same pattern as `/search`:
- Create `SearchSession` with `initial_query = "Best hop → {target_name}"`
- Create `SearchTurn` with:
  - `user_query`: `"Best hop → {target_name}"`
  - `transcript`: `{"type": "best_hop", "target": {name, url}, "mutual_count": N, "matched_count": M, "unmatched_count": U}`
  - `results`: SearchResultItem[] (same schema as regular search results)

No entity changes needed — reuses existing SearchSession/SearchTurn.

### Performance

| Step | Current (agentic) | New (dedicated) |
|------|-------------------|-----------------|
| Web search target | ~4.5s | 0 (pre-assembled) |
| SQL discovery (iterative) | ~4s | ~100ms (batch) |
| Profile lookups (12×) | ~720ms | 0 (in batch) |
| LLM tool orchestration | ~25s (5 LLM calls) | 0 (context injected) |
| LLM ranking + reasoning | — | ~5-8s (1 call) |
| **Total** | **~42s** | **~6-9s** |

---

## Feature: Extraction Speed Control

### UX

Small speed chip `[1x]` shown next to the "page 3/8" extraction progress. Tapping cycles: `1x → 2x → 4x → 8x → 1x`.

```
┌────────────────────────────────┐
│ Extracting mutuals  [4x]      │
│ page 3/8                       │
│ ████████████▓▓▓▓▓▓▓▓          │
│              Cancel            │
└────────────────────────────────┘
```

Adjustable **mid-run** — next page uses updated speed immediately.

### Speed Tiers

| Multiplier | Delay range | Notes |
|-----------|-------------|-------|
| 1x (default) | 2-5s | Current "human-like" behavior |
| 2x | 1-2.5s | |
| 4x | 0.5-1.25s | |
| 8x | 0.25-0.6s | Higher 429 risk |

If LinkedIn returns 429, auto-downshift to 1x.

### State: Service Worker

`bestHopSpeed` lives in `background.ts`. Sidepanel sends `SET_EXTRACTION_SPEED` message to update it. Extractor reads current speed before each page's `sleep()`.

### Implementation

**Extractor change** (`lib/mutual/extractor.ts`):
- Add `getSpeed: () => number` callback parameter
- Before each page sleep: `delay = randomDelay() / getSpeed()`

**Messages** (`lib/messages.ts`):
- New `SetExtractionSpeed` message type: `{ type: 'SET_EXTRACTION_SPEED', multiplier: 1 | 2 | 4 | 8 }`
- New `ExtractionSpeedChanged` message (SW → sidepanel): `{ type: 'EXTRACTION_SPEED_CHANGED', multiplier: number }`

**Service worker** (`entrypoints/background.ts`):
- `let bestHopSpeed = 1`
- Handle `SET_EXTRACTION_SPEED` → update `bestHopSpeed`, broadcast back
- Pass `() => bestHopSpeed` as `getSpeed` callback to extractor

**Sidepanel** (`BestHopPanel.tsx`):
- Speed chip in extracting phase, cycles on tap
- Listens for `EXTRACTION_SPEED_CHANGED` to sync display

---

## Subphases

### A: SSE Helpers Extraction (backend, manual)
Refactor `search_controller.py` → extract shared SSE utilities into `_sse_helpers.py`: `sse_line()`, `stream_with_heartbeat()`, `create_or_resume_session()`, `save_session_state()`. Update `search_controller.py` to import from it.

### B: Best Hop Contracts (backend, `schema-creation-agent`)
Add `BestHopRequest`, `BestHopResultItem` to `contracts.py`.

### C: Best Hop Service (backend, manual)
`best_hop_service.py` — data assembly queries, prompt building, LLM call with context injection, result merge. Not standard CRUD — doesn't extend `BaseService`.

### D: Best Hop Controller (backend, `custom-controller-agent`)
`best_hop_controller.py` — endpoint, SSE streaming using `_sse_helpers.py`, session persistence.

### E: Best Hop Prompt (backend, manual)
`prompts/best_hop_ranking.md` — system prompt template.

### F: Backend Tests
- Service test → `service-test-agent`
- Controller test → `controller-test-agent`
- Integration tests (happy path, all unmatched, partial match) → `integration-test-creator-agent`

### G: Extension — Speed Control (frontend, manual)
Messages, SW state, extractor `getSpeed` callback, `BestHopPanel` speed chip UI.

### H: Extension — Best Hop Client (frontend, manual)
Change `search.ts` to POST structured body to `/best-hop`. Remove `buildQuery()`.

**Dependencies**: A before D. B before C. C+D before F. G and H are independent of backend.

---

## Verification

1. **Unit test**: `best_hop_service` — mock DB session, verify query construction and prompt assembly
2. **Integration test**: POST `/best-hop` with test profiles/connections in test DB, verify SSE event sequence
3. **Integration test — edge cases**:
   - **All URLs unmatched**: POST with URLs not in DB → no `result` events, `done` has `matched=0, unmatched=N`
   - **Partial match**: Mix of known/unknown URLs → correct matched/unmatched counts
4. **Manual E2E**: Trigger from extension on real LinkedIn profile, compare speed and ranking quality vs current flow
5. **Speed control**: Verify mid-run speed changes take effect on next page, verify 429 auto-downshift

## Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| LLM model | Same as search (`SEARCH_LLM_MODEL`) | Consistent, cheap. Structured data doesn't need a stronger model. |
| Target context | DB lookup only, no extension fallback | Extension always enriches target profile on visit before best-hop triggers. |
| Target connection status | Handle both cases | Target may or may not be a connection. Queries 3-4 don't need connection JOIN. If connected, surface affinity as extra LLM context. |
| Speed state | Service worker | Centralized, survives sidepanel re-renders, matches existing message flow. |
| Mid-run speed | Adjustable | Better UX. Extractor reads speed via callback before each page sleep. |
| Result limit | 30 | Enough variety without overwhelming. |
| Unmatched URLs | Report in done event | Transparency. Future: could trigger background enrichment. |
| Session storage | Yes, in existing SearchSession/SearchTurn | History, consistency, future follow-ups. No entity changes needed. |
| LLM control | Pre-assemble context + optional tools | LLM does ranking/reasoning. Tools available as safety net, not expected path. Eliminates 7-iteration discovery without removing LLM from the loop. |
