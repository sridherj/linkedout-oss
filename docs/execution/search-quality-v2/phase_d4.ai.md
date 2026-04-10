# Phase D.4: Simplify Search Controller

**Effort:** ~1 hour
**Dependencies:** Phase D.3 complete (agent is rewired)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Strip the search controller of all session management complexity. Controller becomes a thin layer: receive request, optionally fetch turn history, run agent, write a turn row, stream results.

## What to Do

### 1. Read current controller

**File:** `./src/linkedout/intelligence/controllers/search_controller.py`

Understand what exists:
- `_create_or_resume_session` — to be removed
- `_save_session_state` — to be replaced with simple turn write
- `_handle_pivot` — to be removed
- `get_latest_active` auto-archiving — to be removed
- `agent.excluded_ids`, `agent.current_result_set` reads — to be removed

### 2. Simplify the controller

**File:** `./src/linkedout/intelligence/controllers/search_controller.py`

New flow:
```
1. Receive request with optional session_id
2. If session_id provided:
   a. Fetch session
   b. Fetch turn history: SELECT * FROM search_turn WHERE session_id = ? ORDER BY turn_number
   c. Pass turns to agent via ConversationManager
3. If no session_id:
   a. Create new session (initial_query = user's query)
4. Run agent with turn history (or empty list for new session)
5. After agent completes:
   a. Write a new search_turn row (turn_number = previous max + 1)
   b. Update session.last_active_at and session.turn_count
6. Stream results
```

**Remove:**
- `_create_or_resume_session` method (replace with simple logic above)
- `_save_session_state` method (replace with turn write)
- `_handle_pivot` method
- `get_latest_active` auto-archiving logic
- Reads of `agent.excluded_ids`, `agent.current_result_set` after run
- `exclusion_state` from SSE `conversation_state` event

### 3. Simplify SSE `conversation_state` event

Current event payload:
```json
{
  "result_summary_chips": [...],
  "suggested_actions": [...],
  "exclusion_state": {...},
  "result_metadata": {...},
  "facets": [...]
}
```

New event payload (remove `exclusion_state`):
```json
{
  "result_summary_chips": [...],
  "suggested_actions": [...],
  "result_metadata": {...},
  "facets": [...]
}
```

### 4. Update tests

Update controller tests to:
- Remove tests for pivot detection
- Remove tests for auto-archiving
- Remove tests for exclusion state in SSE events
- Add tests for turn-based flow (new session, continuation with turns)

### 5. Create multi-turn integration test

**NEW file:** `tests/integration/linkedout/intelligence/test_multiturn_integration.py`

Full 4-turn conversation against real DB:
1. **Turn 1 — Narrow:** Initial search (e.g., "find people who can connect me to Palo Alto Networks")
2. **Turn 2 — Broaden:** Broaden results (e.g., "anyone who worked with me")
3. **Turn 3 — Refine:** Add filter (e.g., "who among them are in cybersecurity")
4. **Turn 4 — Verify persistence:** Check that `search_turn` rows were persisted

Assertions:
- Each turn produces non-empty results
- After 4 turns, `SELECT COUNT(*) FROM search_turn WHERE session_id = ?` returns 4
- Turn 3 LLM context includes history from turns 1-2

### 6. Manual 7-turn test scenario

Run this manually after all D sub-phases are complete:

```
Turn 1: "find out folks who can connect me to Palo Alto Networks"
        → results: direct connections + alumni + warm paths
Turn 2: "only people I know very well"
        → narrowed: LLM re-queries with affinity/dunbar filter (NOT filter_results tool)
Turn 3: "never mind, anyone who worked with me"
        → broadened: LLM re-queries without affinity constraint
Turn 4: "who among them are in cybersecurity or infra"
        → refined: LLM adds role/skill filter
Turn 5: "what companies are they at?"
        → aggregation: LLM runs SQL GROUP BY on results
Turn 6: "tag the top 3 as palo-alto-intros"
        → tag tool: persists tags to DB
Turn 7: "show my palo-alto-intros tag"
        → retrieves tagged profiles
```

Verify:
- `SELECT * FROM search_turn WHERE session_id = '...' ORDER BY turn_number` returns 7 rows
- Turn 7 LLM context includes summarized history from earlier turns
- Turn 3 successfully broadens (the original broken case from the problem statement)
- Tags from turn 6 are retrievable in turn 7

## Verification

```bash
# Unit tests
pytest tests/unit/intelligence/ -v

# Integration tests (multi-turn)
pytest tests/integration/linkedout/intelligence/test_multiturn_integration.py -v

# Eval suite (updated multi-turn)
pytest tests/eval/test_multiturn_poc.py -m eval -v

# Precommit
precommit-tests
```

## Key Behavioral Change

After this phase, the backend is **stateless with respect to session decisions:**
- Frontend sends `session_id` → continuation
- Frontend omits `session_id` → new session
- No pivot detection, no auto-archiving, no "one active session" enforcement
