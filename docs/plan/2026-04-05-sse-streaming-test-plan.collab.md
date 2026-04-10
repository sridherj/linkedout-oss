# Test Plan: SSE Streaming — Backend Fix + Full Test Coverage

## Context

The `RequestLoggingMiddleware` in `.` extends Starlette's `BaseHTTPMiddleware`, which buffers SSE streaming responses. The fix (replacing it with pure ASGI middleware) is correct and well-documented. This plan adds proper test coverage for both the fix itself and the SSE pipeline end-to-end across both repos.

---

## Part 1: Backend Tests (`.`)

### 1A. Test the new ASGI middleware preserves streaming

**File**: `tests/unit/shared/utilities/test_request_logging_middleware.py` (new)

Uses a minimal ASGI app that streams chunks, verifies the middleware doesn't buffer them.

```python
# Test cases:
1. test_logs_normal_request — POST /foo returns 200, verify log output (method, path, status, duration)
2. test_streaming_response_not_buffered — SSE endpoint yields 3 chunks with delays,
   verify each chunk arrives at the client before the next is yielded
   (use httpx.AsyncClient with app= for real ASGI testing)
3. test_non_http_scope_passthrough — websocket scope passes through without logging
4. test_status_code_captured — verify 404/500 responses log the correct status code
```

**Key pattern**: Use `httpx.AsyncClient(transport=httpx.ASGITransport(app=...))` to test real ASGI streaming behavior without needing TestClient (which can mask buffering).

**Critical test** (#2): Create a FastAPI app with the middleware, add an SSE endpoint that yields chunks with `asyncio.sleep(0.1)` between them. Read chunks from the async response stream and assert each chunk arrives independently (not all at once at the end). This is the regression test that would have caught the original bug.

### 1B. Test `stream_with_heartbeat` in isolation

**File**: `tests/unit/linkedout/intelligence/test_sse_helpers.py` (new)

```python
# Test cases:
1. test_heartbeat_emitted_after_interval — slow generator (sleeps > interval),
   verify heartbeat event is yielded between real events
2. test_no_heartbeat_when_events_are_fast — generator yields faster than interval,
   verify no heartbeat events in output
3. test_stream_cleanup_on_client_disconnect — cancel the consumer mid-stream,
   verify finally block runs and pending task is cancelled
4. test_heartbeat_format — verify heartbeat is valid SSE: 'data: {"type": "heartbeat"}\n\n'
5. test_sse_line_format — verify sse_line() output matches SSE spec
```

**Pattern**: Use `asyncio.sleep()` in a test async generator to control timing. Set `interval=0.05` for fast tests.

### 1C. Extend existing streaming test for the buffering scenario

**File**: `tests/unit/linkedout/intelligence/test_search_controller_streaming.py` (existing)

```python
# Add:
6. test_heartbeat_reaches_client_during_slow_llm — mock SearchAgent to take 2+ seconds,
   set heartbeat interval to 0.5s, verify heartbeat events appear in the SSE output
   before the final results. This is the exact scenario that was broken.
```

### 1D. Integration test for `/best-hop` SSE stream

**File**: `tests/integration/linkedout/intelligence/test_best_hop_integration.py` (existing)

```python
# Add/verify:
7. test_best_hop_streams_events_incrementally — use httpx.AsyncClient against the real app,
   read chunks as they arrive, verify thinking → result(s) → done ordering
8. test_best_hop_heartbeat_during_slow_service — mock BestHopService to be slow,
   verify heartbeat events arrive while waiting
```

---

## Part 2: Frontend Tests (`<linkedout-fe>`)

### 2A. Extension `streamBestHop` — heartbeat handling

**File**: `extension/lib/backend/__tests__/search.test.ts` (existing)

The existing test already covers result/done/error/thinking events. Add:

```typescript
// Add:
1. test heartbeat events are silently skipped — stream includes heartbeat events
   between results, verify they don't appear in collected events and don't
   break result ordering
2. test stream resilience with interleaved heartbeats — heartbeat between
   every real event, verify all real events still arrive correctly
3. test long-running stream with only heartbeats then results — simulate
   the slow LLM scenario: several heartbeats followed by results, verify
   events arrive in order
```

### 2B. Extension `background.ts` — Best Hop orchestration

**File**: `extension/lib/__tests__/background-best-hop.test.ts` (new)

This is the untested orchestration layer. Test the message relay:

```typescript
// Test cases:
1. test handleFindBestHop broadcasts BEST_HOP_THINKING to side panel
2. test handleFindBestHop broadcasts BEST_HOP_RESULT for each result
3. test handleFindBestHop broadcasts BEST_HOP_COMPLETE on done
4. test handleFindBestHop broadcasts BEST_HOP_ERROR on error
5. test handleCancelBestHop aborts stream and sends completion
6. test concurrent Best Hop requests — second request aborts the first
```

**Pattern**: Mock `streamBestHop` to call the onEvent callback synchronously with test events. Mock `browser.runtime.sendMessage` to capture broadcasts.

### 2C. Web frontend `useStreamingSearch` — heartbeat handling

**File**: `src/__tests__/hooks/useStreamingSearch.test.ts` (existing)

Verify existing coverage includes heartbeat events. Add if missing:

```typescript
// Add:
1. test heartbeat events don't trigger state updates — stream with heartbeats,
   verify no re-renders or state changes from heartbeat events
2. test stream survives extended heartbeat-only period — 5 heartbeats then
   results, verify hook stays in streaming state and doesn't timeout/error
```

---

## Part 3: Files to Modify

| File | Repo | Action |
|------|------|--------|
| `src/shared/utilities/request_logging_middleware.py` | linkedout | Replace `BaseHTTPMiddleware` with pure ASGI |
| `tests/unit/shared/utilities/test_request_logging_middleware.py` | linkedout | **New** — middleware unit tests |
| `tests/unit/linkedout/intelligence/test_sse_helpers.py` | linkedout | **New** — heartbeat/SSE helper tests |
| `tests/unit/linkedout/intelligence/test_search_controller_streaming.py` | linkedout | Add heartbeat-during-slow-LLM test |
| `tests/integration/linkedout/intelligence/test_best_hop_integration.py` | linkedout | Add incremental streaming assertions |
| `extension/lib/backend/__tests__/search.test.ts` | linkedout-fe | Add heartbeat interleaving tests |
| `extension/lib/__tests__/background-best-hop.test.ts` | linkedout-fe | **New** — service worker relay tests |
| `src/__tests__/hooks/useStreamingSearch.test.ts` | linkedout-fe | Add heartbeat resilience tests |

---

## Verification

### Backend
```bash
cd .
# Unit tests (fast, no DB)
pytest tests/unit/shared/utilities/test_request_logging_middleware.py -v
pytest tests/unit/linkedout/intelligence/test_sse_helpers.py -v
pytest tests/unit/linkedout/intelligence/test_search_controller_streaming.py -v

# Integration (needs postgres)
pytest tests/integration/linkedout/intelligence/test_best_hop_integration.py -v -m integration
```

### Frontend
```bash
cd <linkedout-fe>
# Extension tests
cd extension && npx vitest run lib/backend/__tests__/search.test.ts
npx vitest run lib/__tests__/background-best-hop.test.ts

# Web frontend tests
cd .. && npx vitest run src/__tests__/hooks/useStreamingSearch.test.ts
```

### Manual E2E (the real proof)
1. Apply the middleware fix, restart backend
2. Open Chrome **without DevTools**, navigate to a LinkedIn profile with many mutual connections
3. Trigger Best Hop from the extension side panel
4. Verify: "Analyzing" state appears within 15s, results stream in, no timeout
