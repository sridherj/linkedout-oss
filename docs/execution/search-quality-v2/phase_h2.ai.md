# Phase H.2: Update search_conversation_flow Spec

**Effort:** 30 min
**Dependencies:** Phase G complete (frontend implementation must be stable)
**Working directory:** `.`
**Also read:** `<linkedout-fe>/CLAUDE.md`
**Shared context:** `_shared_context.md`

---

## Objective

Update the search_conversation_flow spec to reflect the simplified conversation model.

## What to Do

### 1. Read current spec

**File:** `./docs/specs/search_conversation_flow.collab.md`

### 2. Use the taskos-update-spec agent

Invoke `/taskos-update-spec` with these changes:

**Remove from spec:**
- T10 (Pivot Detection) — entire transition removed
- `exclusionState` from SSE `conversation_state` event
- `ExclusionState` type
- References to `filter_results`, `exclude_from_results`, `rerank_results`, `aggregate_results`, `start_new_search` tools
- Backend auto-archiving behavior

**Update:**
- T7 (Undo/Remove Filter): LLM re-queries with adjusted SQL. No `filter_results` tool.
- T8 (Session Resume): Reads from `search_turn` API instead of `result_snapshot`/`conversation_state`
- T11 (New Search): Simplified to `reset()` + clear session ID. No backend archive call.
- SSE `conversation_state` event: remove `exclusion_state` field
- SSE `session` event: emitted only on new session creation, not on pivots

## Verification

- Spec accurately reflects the implemented frontend (Phase G) and backend (Phase D)
- All transition descriptions match actual behavior
- SSE protocol section matches actual events
