# Sub-phase A: SSE Helpers Extraction

**Effort:** 30-45 minutes
**Dependencies:** None (can start immediately)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Extract shared SSE utilities from `search_controller.py` into a new `_sse_helpers.py` module so that `best_hop_controller.py` (subphase D) can reuse them without duplicating code.

## What to Do

### 1. Create `_sse_helpers.py`

**File:** `src/linkedout/intelligence/controllers/_sse_helpers.py`

Extract these functions from `search_controller.py`:

- `_sse_line(event: dict) -> str` — serialize one SSE event as `data: {json}\n\n`
- `_stream_with_heartbeat(stream: AsyncGenerator[str, None]) -> AsyncGenerator[str, None]` — wrap any SSE generator with periodic heartbeats. **Refactor** the current implementation to accept a generic `AsyncGenerator` instead of being hard-wired to `_stream_search`'s specific parameters.
- `_create_or_resume_session(tenant_id, bu_id, app_user_id, query, session_id) -> tuple[str, list[dict] | None]` — create/resume SearchSession
- `_save_session_state(session_id, user_query, turn_response, explanations) -> None` — persist turn data

Also extract the constant:
- `_HEARTBEAT_INTERVAL = 15`

### 2. Update `search_controller.py`

Replace the extracted functions with imports from `_sse_helpers`:

```python
from linkedout.intelligence.controllers._sse_helpers import (
    sse_line,
    stream_with_heartbeat,
    create_or_resume_session,
    save_session_state,
    HEARTBEAT_INTERVAL,
)
```

Drop the leading underscore from function names since they're now a shared module (public API within the package).

Update `_stream_search` to pass its generator to the refactored `stream_with_heartbeat()`.

Update `search()` endpoint to use the new imports.

### 3. Naming Convention

In the new module, use **public names** (no underscore prefix):
- `sse_line()` (was `_sse_line`)
- `stream_with_heartbeat()` (was `_stream_with_heartbeat`)
- `create_or_resume_session()` (was `_create_or_resume_session`)
- `save_session_state()` (was `_save_session_state`)
- `HEARTBEAT_INTERVAL` (was `_HEARTBEAT_INTERVAL`)

## Key Refactoring Detail

The current `_stream_with_heartbeat` takes `(tenant_id, bu_id, app_user_id, request, explain)` and internally calls `_stream_search`. Refactor to accept a generic `AsyncGenerator[str, None]` so it can wrap any SSE stream:

```python
async def stream_with_heartbeat(
    stream: AsyncGenerator[str, None],
    interval: int = HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    ...
```

The `search()` endpoint then does:
```python
stream_with_heartbeat(_stream_search(tenant_id, bu_id, app_user_id, request, explain))
```

## Verification

```bash
# All existing search tests still pass
pytest tests/ -k "search" -v

# Import check
python -c "from linkedout.intelligence.controllers._sse_helpers import sse_line, stream_with_heartbeat, create_or_resume_session, save_session_state"

# Smoke test: existing /search endpoint still works (manual or integration test)
```

## What NOT to Do

- Do not change any SSE behavior or event format
- Do not modify the `_stream_search` generator logic
- Do not add new functionality — pure refactoring extraction
