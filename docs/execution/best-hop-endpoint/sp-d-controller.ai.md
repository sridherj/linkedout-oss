# Sub-phase D: Best Hop Controller

**Effort:** 1-2 sessions
**Dependencies:** A (SSE helpers), B (contracts — via C which depends on B)
**Working directory:** `.`
**Shared context:** `_shared_context.md`
**Agent:** `custom-controller-agent`

---

## Objective

Create `best_hop_controller.py` — the `POST /best-hop` SSE streaming endpoint using extracted SSE helpers from subphase A.

## What to Do

### 1. Create controller file

**File:** `src/linkedout/intelligence/controllers/best_hop_controller.py`

### 2. Router Setup

```python
best_hop_router = APIRouter(
    prefix="/tenants/{tenant_id}/bus/{bu_id}",
    tags=["best-hop"],
)
```

### 3. Endpoint

```python
@best_hop_router.post("/best-hop")
async def best_hop(
    tenant_id: str,
    bu_id: str,
    request: BestHopRequest,
    app_user_id: str = Header(..., alias="X-App-User-Id"),
):
    """SSE streaming best-hop ranking endpoint."""
    return StreamingResponse(
        stream_with_heartbeat(_stream_best_hop(tenant_id, bu_id, app_user_id, request)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

### 4. SSE Stream Generator

```python
async def _stream_best_hop(
    tenant_id: str,
    bu_id: str,
    app_user_id: str,
    request: BestHopRequest,
) -> AsyncGenerator[str, None]:
```

**Event sequence:**
1. `yield sse_line({"type": "thinking", "message": "Assembling context..."})`
2. Create/resume session via `create_or_resume_session()` with query = `"Best hop → {request.target_name}"`
3. `yield sse_line({"type": "session", "payload": {"session_id": session_id}})`
4. `yield sse_line({"type": "thinking", "message": "Found {matched} of {total} mutual connections..."})`
5. Run `BestHopService.rank()` in a thread — yield each `BestHopResultItem` as `result` event
6. `yield sse_line({"type": "done", "payload": {"total": N, "matched": M, "unmatched": U, "session_id": session_id}})`
7. Persist session state (fire-and-forget) via `save_session_state()`

**Thread execution:** Use `asyncio.to_thread()` for the synchronous `BestHopService` methods, same pattern as `search_controller.py`.

**Error handling:** Catch exceptions, yield `{"type": "error", "message": str(e)}`.

### 5. Session Persistence

Reuse existing `SearchSession` / `SearchTurn` entities:

```python
save_session_state(
    session_id=session_id,
    user_query=f"Best hop → {request.target_name}",
    turn_response=ConversationTurnResponse(
        message=f"Ranked {len(results)} mutual connections for intro to {request.target_name}",
        results=[...],  # Convert BestHopResultItem to SearchResultItem
        ...
    ),
)
```

Note: `save_session_state` expects a `ConversationTurnResponse`. Either adapt it to accept a simpler structure, or build a minimal `ConversationTurnResponse` from best-hop results.

### 6. Register Router

**File:** `src/linkedout/main.py`

Add:
```python
from linkedout.intelligence.controllers.best_hop_controller import best_hop_router
app.include_router(best_hop_router)
```

## Imports

```python
from linkedout.intelligence.contracts import BestHopRequest, BestHopResultItem
from linkedout.intelligence.controllers._sse_helpers import (
    sse_line,
    stream_with_heartbeat,
    create_or_resume_session,
    save_session_state,
)
from linkedout.intelligence.services.best_hop_service import BestHopService
from shared.infra.db.db_session_manager import db_session_manager
```

## Verification

```bash
# Import check
python -c "from linkedout.intelligence.controllers.best_hop_controller import best_hop_router"

# App starts without errors
python -c "from linkedout.main import app; print('OK')"

# Integration: POST /best-hop returns SSE stream (subphase F)
```

## What NOT to Do

- Do not duplicate SSE helper logic — import from `_sse_helpers`
- Do not add explanation/enrichment logic (WhyThisProfile) — the LLM's `why_this_person` IS the explanation
- Do not create new entity types — reuse SearchSession/SearchTurn
