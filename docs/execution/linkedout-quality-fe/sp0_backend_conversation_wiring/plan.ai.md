# Sub-phase 0: Wire run_turn() into SSE Controller

> **Pre-requisite:** Read `./docs/execution/linkedout-quality-fe/_shared_context.md` before starting this sub-phase.

## Objective

Wire the existing `SearchAgent.run_turn()` method into the SSE search controller so that multi-turn conversation data (result_summary_chips, suggested_actions, exclusion_state, result_metadata, facets) is streamed to the frontend. Currently `run_turn()` exists and returns a full `ConversationTurnResponse`, but the controller only calls `agent.run()` and ignores the conversational fields.

This is a **backend-only** sub-phase. It must complete before the frontend conversation thread (SP3) can be implemented.

## Dependencies
- **Requires completed:** None (backend code already exists, just needs wiring)
- **Blocks:** SP3 (Conversation Thread frontend)

## Current State

### What exists:
- `SearchAgent.run_turn()` at `./src/linkedout/intelligence/agents/search_agent.py:964` — fully implemented, returns `ConversationTurnResponse` with:
  - `message`, `results`, `query_type`
  - `result_summary_chips: list[ResultSummaryChip]`
  - `suggested_actions: list[SuggestedAction]`
  - `exclusion_state: ExclusionState`
  - `result_metadata: ResultMetadata`
  - `facets: list[FacetGroup]`
  - `turn_transcript: list[dict]`
  - `input_token_estimate`, `output_token_estimate`
- `SearchRequest` at `./src/linkedout/intelligence/contracts.py:36` — already has `session_id` and `conversation_state` fields
- SSE controller at `./src/linkedout/intelligence/controllers/search_controller.py` — `_stream_search()` at line 308 currently calls `agent.run()`, NOT `agent.run_turn()`

### What's missing:
1. Controller doesn't call `run_turn()` — it calls `run()` which returns basic `SearchAgentResponse` (results + answer + query_type only)
2. No SSE event for conversation state — `result_summary_chips`, `suggested_actions`, `exclusion_state`, `result_metadata`, `facets` are never sent to frontend
3. `run_turn()` needs `result_set` and `excluded_ids` from session state, but the controller doesn't load/pass these
4. Session persistence doesn't save `excluded_ids` or `conversation_state` from `run_turn()` output

## Scope
**In scope:**
- Replace `agent.run()` with `agent.run_turn()` for ALL searches (no backward compatibility needed — `run_turn()` handles first-turn and multi-turn uniformly)
- Add a new `conversation_state` SSE event that sends `ConversationTurnResponse` fields to the frontend
- Load `result_set` and `excluded_ids` from session state and pass to `run_turn()`
- Update `_save_session_state()` to persist `excluded_ids`, full `conversation_state`, and `result_set` from `run_turn()` output
- Remove the old `agent.run()` call path entirely
- Write/update unit tests

**Out of scope:**
- Frontend changes (that's SP1-SP3)
- Changes to `run_turn()` itself (already works)
- New API endpoints

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `./src/linkedout/intelligence/controllers/search_controller.py` | Modify | Wire `run_turn()` into `_stream_search()`, add conversation_state SSE event, update `_save_session_state()` |
| `./src/linkedout/intelligence/contracts.py` | Possibly modify | May need to add `ConversationTurnResponse` to imports if not already exported |
| `./tests/unit/intelligence/` | Create/Modify | Test the new SSE event and session state persistence |

## Detailed Steps

### Step 0.1: Update `_stream_search()` to use `run_turn()` for multi-turn

In `./src/linkedout/intelligence/controllers/search_controller.py`, the `_run_agent()` inner function (line 334) currently does:

```python
agent = SearchAgent(session=session, app_user_id=app_user_id)
response = agent.run(query=request.query, conversation_state=effective_conv_state)
return response.results, response.query_type, response.answer
```

Replace with `run_turn()` for ALL searches (no backward compat needed):

```python
agent = SearchAgent(session=session, app_user_id=app_user_id)

# Load result set and excluded IDs from session state (None for first turn)
result_set = _load_result_set_from_session(search_session_id)
excluded_ids = _load_excluded_ids_from_session(search_session_id)

turn_response = agent.run_turn(
    query=request.query,
    conversation_state=effective_conv_state,
    result_set=result_set,
    excluded_ids=excluded_ids,
)
return turn_response
```

Remove the old `agent.run()` call path entirely.

### Step 0.2: Add `conversation_state` SSE event

After streaming individual results, if the response is a `ConversationTurnResponse`, emit a new SSE event:

```python
yield _sse_line({
    "type": "conversation_state",
    "payload": {
        "result_summary_chips": [chip.model_dump() for chip in turn_response.result_summary_chips],
        "suggested_actions": [action.model_dump() for action in turn_response.suggested_actions],
        "exclusion_state": turn_response.exclusion_state.model_dump(),
        "result_metadata": turn_response.result_metadata.model_dump(),
        "facets": [fg.model_dump() for fg in turn_response.facets],
    },
})
```

This event should be sent after `explanations` and before `done`.

### Step 0.3: Load session state for multi-turn

Add helper functions to load `result_set` and `excluded_ids` from the session's JSONB fields:

```python
def _load_result_set_from_session(session_id: str) -> list[dict] | None:
    """Load the last result snapshot from session for in-memory tools."""
    with db_session_manager.get_session(DbSessionType.READ) as db:
        service = SearchSessionService(db)
        session = service.get_entity_by_id(session_id)
        if session and session.result_snapshot:
            return session.result_snapshot if isinstance(session.result_snapshot, list) else None
    return None

def _load_excluded_ids_from_session(session_id: str) -> list[str] | None:
    """Load excluded profile IDs from session."""
    with db_session_manager.get_session(DbSessionType.READ) as db:
        service = SearchSessionService(db)
        session = service.get_entity_by_id(session_id)
        if session and session.excluded_ids:
            return session.excluded_ids
    return None
```

### Step 0.4: Update `_save_session_state()` for multi-turn

The current `_save_session_state()` at line 282 saves `result_snapshot` and `conversation_state.messages`. Extend it to also save:
- `excluded_ids` from `agent.excluded_ids` property
- Full result set from `agent.current_result_set` property
- `turn_transcript` from `ConversationTurnResponse`

### Step 0.5: Tests

- Test that ALL searches (first-turn and multi-turn) emit the `conversation_state` SSE event
- Test that `_save_session_state()` persists excluded_ids and result set
- Test that `_load_result_set_from_session()` returns correct data
- Test that the old `agent.run()` code path is removed

## Verification
- [ ] `pytest tests/unit/intelligence/` passes
- [ ] `pytest tests/unit/` passes (no regressions)
- [ ] ALL searches use `run_turn()` — no `agent.run()` call remains in controller
- [ ] SSE stream includes `conversation_state` event with chips, actions, exclusion state, metadata, facets
- [ ] Session state includes `excluded_ids` and `result_set` after save
