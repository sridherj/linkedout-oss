# Sub-Phase 4: SSE Search Endpoint + Why This Person Explainer

**Goal:** linkedin-ai-production
**Phase:** 4 — Intelligence: Search Engine + Affinity Scoring
**Depends on:** SP-3 (SearchAgent Core)
**Estimated effort:** 2-3h
**Source plan sections:** 4.3, 4.6

---

## Objective

Build the async SSE streaming search endpoint and the "Why This Person" explainer that adds 1-sentence explanations to search results. This sub-phase delivers the user-facing search API.

## Context

The SSE pattern was validated in S8 spike (`src/shared/test_endpoints/sse_router.py`). Key insight: `asyncio.to_thread()` bridges sync DB/SearchAgent from async endpoints. The explainer runs after results are fetched, adding an `explanations` SSE event.

## Pre-Flight Checks

Before starting, verify these exist:
- [ ] `src/linkedout/intelligence/agents/search_agent.py` — `SearchAgent` (SP-3 output)
- [ ] `src/linkedout/intelligence/contracts.py` — `SearchRequest`, `SearchEvent`, `SearchResultItem` (SP-3 output)
- [ ] `src/shared/test_endpoints/sse_router.py` — SSE spike for reference patterns
- [ ] `main.py` — knows how to register routers

## Files to Create

```
src/linkedout/intelligence/
├── controllers/
│   ├── __init__.py
│   └── search_controller.py         # SSE search endpoint
└── explainer/
    ├── __init__.py
    └── why_this_person.py            # WhyThisPersonExplainer
```

---

## Step 1: SSE Search Endpoint (`search_controller.py`)

```python
search_router = APIRouter(
    prefix='/tenants/{tenant_id}/bus/{bu_id}',
    tags=['search']
)

@search_router.post('/search')
async def search(
    tenant_id: str,
    bu_id: str,
    request: SearchRequest,
    app_user_id: str = Header(..., alias='X-App-User-Id'),
):
    """SSE streaming search endpoint."""
    return StreamingResponse(
        _stream_search(tenant_id, bu_id, app_user_id, request),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )
```

**Key patterns (from S8 spike):**
- `async def` endpoint with `StreamingResponse`
- `asyncio.to_thread()` wraps sync `DbSessionManager` + `SearchAgent.run()` calls
- Heartbeat: send `data: {"type": "heartbeat"}\n\n` every 15s to prevent idle timeout
- On error: send `{"type": "error", "message": "..."}` event then close stream
- Each SSE event formatted as: `data: {json}\n\n`

**`_stream_search` generator:**
1. Yield `{"type": "thinking", "message": "Starting search..."}`
2. Run `SearchAgent.run_streaming()` via `asyncio.to_thread()` (or consume its async generator)
3. Yield each `SearchEvent` from the agent
4. After results stream, run `WhyThisPersonExplainer` → yield `{"type": "explanations", "payload": {...}}`
5. Yield `{"type": "done", "payload": {"total": N, "query_type": "..."}}`
6. On error: yield `{"type": "error", "message": "..."}` and return

---

## Step 2: Why This Person Explainer (`why_this_person.py`)

```python
class WhyThisPersonExplainer:
    def __init__(self, llm_client):
        self._client = llm_client

    def explain(self, query: str, results: list[SearchResultItem]) -> dict[str, str]:
        """Returns {connection_id: "1-sentence explanation"} for each result."""
```

**Implementation:**
1. Format prompt with query + result summaries (name, position, company, location, affinity)
2. Single LLM call (gpt-5.4-mini) — cost ~$0.01/search
3. Parse response into `{connection_id: explanation}` dict
4. Latency: ~1s added. Runs after results stream, so user sees results first, then explanations arrive

**Prompt template:**
```
For each person below, write a 1-sentence explanation of why they match the query "{query}".
Focus on: relevant experience, skills, company, location, or affinity signals.
Format: one line per person, "ID: explanation"

Results:
{formatted_results}
```

**SSE integration:** After all `result` events stream, the endpoint emits:
```json
{"type": "explanations", "payload": {"conn_123": "3 years at YC startups, Python focus, based in SF"}}
```
The frontend patches `why_this_person` onto result cards when this event arrives.

**Optional disable:** `?explain=false` query param skips the explainer call (useful for lower latency).

---

## Step 3: Register Router

Add `search_router` to `main.py`:
```python
from src.linkedout.intelligence.controllers.search_controller import search_router
app.include_router(search_router)
```

---

## Step 4: Unit Tests

Create `tests/unit/linkedout/intelligence/test_why_this_person.py`:
- Prompt formatting with query + results
- Response parsing (multi-line "ID: explanation" format)
- Handles missing/extra IDs gracefully
- Mock LLM client

---

## Step 5: Manual Smoke Test

After wiring everything up:
```bash
curl -N -X POST http://localhost:8000/tenants/sys_tenant_1/bus/sys_bu_1/search \
  -H "Content-Type: application/json" \
  -H "X-App-User-Id: usr_sj" \
  -d '{"query": "engineers at Google"}'
```

Expected: SSE events stream with `thinking` → `result` (multiple) → `explanations` → `done`.

---

## Completion Criteria

- [ ] `POST /tenants/{tid}/bus/{bid}/search` returns SSE stream
- [ ] SSE events follow the contract: thinking, result, explanations, done, error
- [ ] Heartbeat sent every 15s to prevent idle timeout
- [ ] `WhyThisPersonExplainer` generates 1-sentence explanations per result
- [ ] Explanations arrive as a separate SSE event after all results
- [ ] `?explain=false` skips the explainer
- [ ] Router registered in `main.py`
- [ ] Unit tests pass for WhyThisPersonExplainer
- [ ] Manual curl smoke test shows streaming events
