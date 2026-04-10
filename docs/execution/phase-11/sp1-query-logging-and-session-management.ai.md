# Sub-Phase 1: Query Logging Module + Session Management

**Phase:** 11 — Query History & Reporting
**Plan tasks:** 11A (Query Logging Module), 11B (Session Management)
**Dependencies:** Phase 3 (metrics, logging infrastructure), Phase 8 (skill template system)
**Blocks:** sp3, sp4, sp6
**Can run in parallel with:** sp2

## Objective
Build the file-based query logging module that records every skill-driven query as JSONL, and the session management layer that groups related queries into conversations. This is the data write path — all three skills depend on the data these modules produce.

## Context
- Read shared context: `docs/execution/phase-11/_shared_context.md`
- Read plan (11A + 11B sections): `docs/plan/phase-11-query-history.md`
- Read config design decision: `docs/decision/env-config-design.md`
- Read data directory convention: `docs/decision/2026-04-07-data-directory-convention.md`
- Read logging strategy: `docs/decision/logging-observability-strategy.md`

## Deliverables

### 1. `backend/src/linkedout/query_history/__init__.py` (NEW)
Package init. Export the main public API:
```python
from linkedout.query_history.query_logger import log_query
from linkedout.query_history.session_manager import get_or_create_session, start_new_session
```

### 2. `backend/src/linkedout/query_history/query_logger.py` (NEW)

The core query logging module. All writes go to `~/linkedout-data/queries/`.

**`log_query()` function:**
- Signature: `log_query(query_text: str, query_type: str = "general", result_count: int = 0, duration_ms: int = 0, model_used: str = "", session_id: str | None = None, is_refinement: bool = False) -> str`
- Returns: the generated `query_id`
- Generates `query_id` using nanoid with prefix `q_` (e.g., `q_V1StGXR8_Z5jdHi6B-myT`)
- Appends a single JSON line to `~/linkedout-data/queries/YYYY-MM-DD.jsonl` (today's date)
- JSONL entry fields: `timestamp` (ISO 8601), `query_id`, `session_id`, `query_text`, `query_type`, `result_count`, `duration_ms`, `model_used`, `is_refinement`
- If `session_id` is None, creates a new session via `session_manager.start_new_session()` and uses that ID
- Directory and file created lazily on first write
- Thread-safe: uses `fcntl.flock()` advisory lock on the JSONL file for concurrent writes
- Respects `LINKEDOUT_DATA_DIR` env var override for all paths (default: `~/linkedout-data/`)

**Metrics integration:**
- After writing JSONL, calls `record_metric("query", value=1, metadata={"query_type": query_type, "result_count": result_count, "duration_ms": duration_ms})` from the Phase 3I metrics module
- If `record_metric` is not available (Phase 3 not yet implemented), catch `ImportError` and skip gracefully

**Logging integration:**
- Logs a summary line via `get_logger(component="skill", operation="query")`:
  `query_logger.info("Query logged", query_id=query_id, query_type=query_type, result_count=result_count, duration_ms=duration_ms)`
- If `get_logger` is not available, fall back to standard `logging` module

**Helper functions:**
- `get_queries_dir() -> Path` — resolve `~/linkedout-data/queries/` with `LINKEDOUT_DATA_DIR` override
- `get_today_file() -> Path` — resolve today's JSONL file path

### 3. `backend/src/linkedout/query_history/session_manager.py` (NEW)

Session management for grouping related queries.

**Session file:** `~/linkedout-data/queries/.active_session.json`

**Session JSON schema:**
```json
{
  "session_id": "s_V1StGXR8_Z5jdHi6B-myT",
  "initial_query": "who do I know at Stripe?",
  "started_at": "2026-04-07T14:23:00Z",
  "last_query_at": "2026-04-07T14:25:30Z",
  "turn_count": 3
}
```

**`get_or_create_session(query_text: str, timeout_minutes: int = 30) -> tuple[str, bool]`**
- Returns: `(session_id, is_new_session)`
- If no active session file exists, creates a new session
- If active session exists but `last_query_at` is older than `timeout_minutes`, creates a new session
- If active session exists and is within timeout, updates `last_query_at` and increments `turn_count`, returns existing `session_id` with `is_new_session=False`
- Timeout configurable via `LINKEDOUT_SESSION_TIMEOUT_MINUTES` env var (default: 30)

**`start_new_session(query_text: str) -> str`**
- Creates a new session unconditionally
- Generates `session_id` with prefix `s_`
- Writes `.active_session.json`
- Returns the new `session_id`

**`get_active_session() -> dict | None`**
- Returns the current active session data, or None if no session file

### 4. Unit Tests

**`backend/tests/unit/query_history/test_query_logger.py` (NEW)**
- Test JSONL entry contains all required fields
- Test file is created in correct date-based path
- Test `query_id` has `q_` prefix
- Test `session_id` is auto-generated when not provided
- Test `LINKEDOUT_DATA_DIR` override changes output path
- Test concurrent writes from threads don't corrupt the file (use `threading`)
- Test concurrent writes from separate processes don't corrupt the file (use `multiprocessing` — two Claude sessions invoking `/linkedout` simultaneously is realistic; `fcntl.flock()` must protect across processes, not just threads). Spawn 2-4 child processes each writing 50 entries, then read back and verify all entries are valid JSON lines with no interleaving.
- Test directory is created lazily on first write

**`backend/tests/unit/query_history/test_session_manager.py` (NEW)**
- Test new session creation when no active session exists
- Test session continuation within timeout
- Test new session creation on timeout expiry
- Test `start_new_session()` always creates new
- Test session_id has `s_` prefix
- Test `LINKEDOUT_SESSION_TIMEOUT_MINUTES` env var override
- Test `.active_session.json` file lifecycle

## Verification
After completing all deliverables, run:
```bash
cd backend && uv run pytest tests/unit/query_history/ -v
```
All tests must pass. Also verify:
- `log_query("test query")` creates a JSONL file in a temp directory
- JSONL is valid JSON per line
- Session file is correctly read/written
