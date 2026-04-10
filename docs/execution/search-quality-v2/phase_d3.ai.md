# Phase D.3: Rewire SearchAgent + Remove Result Set Tools

**Effort:** ~1-2 hours
**Dependencies:** Phase D.2 complete (needs ConversationManager)
**Working directory:** `.`
**Shared context:** `_shared_context.md`

---

## Objective

Rewire the SearchAgent to use ConversationManager for history, and remove the result set tools (filter/exclude/rerank/aggregate/start_new_search) that are being replaced by the LLM's natural re-querying behavior.

## What to Do

### 1. Read current SearchAgent implementation

**File:** `./src/linkedout/intelligence/agents/search_agent.py`

Understand:
- `_inject_conversation_history()` — to be replaced
- `_current_result_set`, `_excluded_ids`, `_pivot_detected` state — to be removed
- How result set tools are registered and dispatched

### 2. Rewire SearchAgent to use ConversationManager

**File:** `./src/linkedout/intelligence/agents/search_agent.py`

Changes:
- Import `ConversationManager`
- Initialize ConversationManager with summarization prompt loaded via PromptManager (key: `intelligence/summarize_turns`)
- Replace `_inject_conversation_history()` call with `conversation_manager.build_history(turns)`
- The agent's `run()` method should accept turn history (list of turn dicts from DB) as a parameter
- Remove `_inject_conversation_history()` method entirely

### 3. Remove result set tools

**File:** `./src/linkedout/intelligence/agents/search_agent.py`

Remove from `_TOOL_DEFINITIONS`:
- `filter_results`
- `exclude_from_results`
- `rerank_results`
- `aggregate_results`
- `start_new_search`

Remove from `_execute_tool()` dispatch.

Remove instance state:
- `_current_result_set`
- `_excluded_ids`
- `_pivot_detected`

**Keep:**
- `tag_profiles` (DB-persisted, useful)
- `get_tagged_profiles` (DB-persisted, useful)
- `compute_facets` (used for UI facets)

### 4. Clean up result_set_tool.py

**File:** `./src/linkedout/intelligence/tools/result_set_tool.py`

Remove functions:
- `filter_results`
- `exclude_from_results`
- `rerank_results`
- `aggregate_results`

Keep:
- `tag_profiles`
- `get_tagged_profiles`
- `compute_facets`

### 5. Clean up contracts

**File:** `./src/linkedout/intelligence/contracts.py`

Remove:
- `ContextStrategy` enum
- `ConversationState` class
- `ConversationConfig` class
- `ExclusionState` class

Keep all other contracts.

### 6. Update search system prompt

**File:** `./src/linkedout/intelligence/prompts/search_system.md`

Remove any remaining references to result set tools (filter/exclude/rerank/aggregate/start_new_search). Keep references to tag_profiles and compute_facets.

### 7. Update tests

Update existing tests in `./tests/unit/intelligence/` to:
- Remove tests for deleted result set tools
- Update SearchAgent tests for new `run()` signature (accepts turn history)
- Add test: agent with conversation history uses ConversationManager

### 8. Rewrite eval files

#### a. Rewrite `tests/eval/multi_turn_runner.py`

Remove imports/references to:
- `ContextStrategy`
- `ConversationState`
- `ConversationConfig`

Replace with:
- Use `ConversationManager` for building conversation history
- Use `search_turn` rows (from DB or in-memory list) as the history source
- The runner should replay turns sequentially, each time building history from prior turn rows via ConversationManager

#### b. Rewrite `tests/eval/test_multiturn_poc.py`

Remove:
- All `ContextStrategy` references (enum was deleted in step 5)
- Multiple replay modes — single replay mode only, via `ConversationManager`

Update the 5-turn scenario:
- Turn 1-3: keep as-is (initial search, narrow, broaden)
- Turn 4: was "exclude these people" using `exclude_from_results` → change to a **re-query** (e.g., "show me only people NOT at big tech companies" — LLM re-queries with exclusion in SQL WHERE clause)
- Turn 5: was "aggregate by company" using `aggregate_results` → change to **SQL aggregation** (e.g., "what companies are they at?" — LLM runs `GROUP BY` query)

The test should verify:
- All 5 turns produce non-empty results
- Turn history is correctly built via ConversationManager
- No references to removed tools/contracts remain

## Verification

```bash
# Unit tests
pytest tests/unit/intelligence/ -v

# Verify removed artifacts don't exist
# grep: filter_results, exclude_from_results, rerank_results, aggregate_results, start_new_search
#   should NOT appear in _TOOL_DEFINITIONS or _execute_tool()
# grep: _current_result_set, _excluded_ids, _pivot_detected
#   should NOT appear in search_agent.py
# grep: ContextStrategy, ConversationState, ConversationConfig
#   should NOT appear in contracts.py

# Precommit
precommit-tests
```

## Caution

This is a large, coordinated change across multiple files. Make all changes together — partial application will break the agent. Consider doing this in a single commit.
